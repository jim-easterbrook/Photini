//  Photini - a simple photo metadata editor.
//  http://github.com/jim-easterbrook/Photini
//  Copyright (C) 2024  Jim Easterbrook  jim@jim-easterbrook.me.uk
//
//  This file is part of Photini.
//
//  Photini is free software: you can redistribute it and/or modify it
//  under the terms of the GNU General Public License as published by the
//  Free Software Foundation, either version 3 of the License, or (at
//  your option) any later version.
//
//  Photini is distributed in the hope that it will be useful, but
//  WITHOUT ANY WARRANTY; without even the implied warranty of
//  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
//  General Public License for more details.
//
//  You should have received a copy of the GNU General Public License
//  along with Photini.  If not, see <http://www.gnu.org/licenses/>.


// See https://learn.microsoft.com/en-us/javascript/api/azure-maps-control/atlas.map

const BBox = atlas.data.BoundingBox;
const Pos = atlas.data.Position;
const Pxl = atlas.Pixel;

var map;
var layers = [];
var padding = {top: 40, bottom: 5, left: 18, right: 18};

function loadMap(lat, lng, zoom, options) {
    options.center = [lng, lat];
    options.dragRotateInteraction = false;
    options.maxZoom = 19;
    options.zoom = zoom - 1;
    map = new atlas.Map("mapDiv", options);
    //Wait until the map resources are ready.
    map.events.add('ready', mapReady);
}

function mapReady() {
    map.controls.add(
        [new atlas.control.StyleControl({
            mapStyles: ['road', 'road_shaded_relief',
                        'satellite', 'satellite_road_labels'],
            layout: 'list'}),
         new atlas.control.ZoomControl()],
        {position: 'top-right'});
    map.controls.add(
        [new atlas.control.ScaleControl()],
        {position: 'bottom-left'});
    map.events.add('dragend', newBounds);
    map.events.add('moveend', newBounds);
    map.events.add('zoomend', newBounds);
    for (var i = 0; i < 2; i++) {
        layers.push(new atlas.source.DataSource());
        map.sources.add(layers[i]);
    }
    // Load GPS marker image data
    var promises = [
        map.imageSprite.add('circle_red', circle_red_data),
        map.imageSprite.add('circle_blue', circle_blue_data),
    ];
    // Once loaded, set up GPS marker data layers
    Promise.all(promises).then(function () {
        var symbolLayer = new atlas.layer.SymbolLayer(layers[0], null, {
            iconOptions: {
                allowOverlap: false,
                ignorePlacement: true,
                image: 'circle_blue',
                anchor: 'top-left',
                offset: [-5, -5],
            }});
        map.layers.add(symbolLayer);
        symbolLayer = new atlas.layer.SymbolLayer(layers[1], null, {
            iconOptions: {
                allowOverlap: true,
                ignorePlacement: true,
                image: 'circle_red',
                anchor: 'top-left',
                offset: [-5, -5],
            }});
        map.layers.add(symbolLayer);
        python.initialize_finished();
        newBounds();
    });
}

//function newCredentials(sessionId) {
//    python.new_status({
//        session_id: sessionId,
//        });
//    python.initialize_finished();
//}

function newBounds() {
    var camera = map.getCamera();
    python.new_status({
        centre: [camera.center[1], camera.center[0]],
        bounds: [camera.bounds[3], camera.bounds[2],
                 camera.bounds[1], camera.bounds[0]],
        zoom: camera.zoom + 1,
        });
}

function setView(lat, lng, zoom) {
    map.setCamera({center: [lng, lat], zoom: zoom - 1});
}

function adjustBounds(north, east, south, west) {
    map.setCamera({bounds: [west, south, east, north], padding: padding});
}

function fitPoints(points) {
    var positions = [];
    for (i in points)
        // NB fromLatLng params are lng, lat
        positions.push(Pos.fromLatLng(points[i][1], points[i][0]));
    var bounds = BBox.fromPositions(positions);
    var mapBounds = map.getCamera().bounds;
    // Reduce map bounds to allow for padding
    var zoom = map.getCamera().zoom;
    positions = [BBox.getNorthEast(mapBounds), BBox.getSouthWest(mapBounds)];
    pixels = atlas.math.mercatorPositionsToPixels(positions, zoom);
    pixels = [
        Pxl(Pxl.getX(pixels[0]) - padding.right,
            Pxl.getY(pixels[0]) + padding.top),
        Pxl(Pxl.getX(pixels[1]) + padding.left,
            Pxl.getY(pixels[1]) - padding.bottom)];
    positions = atlas.math.mercatorPixelsToPositions(pixels, zoom);
    mapBounds = BBox.fromPositions(positions);
    // Get opposite corners of points bounding box
    var ne = BBox.getNorthEast(bounds);
    var sw = BBox.getSouthWest(bounds);
    if (BBox.containsPosition(mapBounds, ne) &&
        BBox.containsPosition(mapBounds, sw))
        return;
    // Compute minimum map pan required
    var dx = Math.max(0, ne[0] - BBox.getEast(mapBounds));
    dx = Math.min(dx, sw[0] - BBox.getWest(mapBounds));
    var dy = Math.max(0, ne[1] - BBox.getNorth(mapBounds));
    dy = Math.min(dy, sw[1] - BBox.getSouth(mapBounds));
    // Jump, pan or zoom out?
    var map_h = BBox.getHeight(mapBounds);
    var map_w = BBox.getWidth(mapBounds);
    var bounds_h = BBox.getHeight(bounds);
    var bounds_w = BBox.getWidth(bounds);
    var options = {};
    if (bounds_h > map_h || bounds_w > map_w) {
        // Zoom out
        options = {bounds: bounds, padding: padding};
        map_h = Math.max(map_h, bounds_h);
        map_w = Math.max(map_w, bounds_w);
    }
    else {
        // Don't zoom in
        options = {zoom: zoom};
        if (Math.abs(dx) > map_w * 2 || Math.abs(dy) > map_h * 2)
            options.center = BBox.getCenter(bounds);
        else {
            var centre = map.getCamera().center;
            options.center = Pos.fromLatLng(centre[0] + dx, centre[1] + dy);
        }
    }
    if (Math.abs(dx) > map_w * 2 || Math.abs(dy) > map_h * 2)
        options.type = 'jump';
    else {
        options.type = 'ease';
        options.duration = 250;
    }
    map.setCamera(options);
}

function plotGPS(points) {
    for (i in points) {
        layers[0].add(new atlas.data.Feature(
            new atlas.data.Point([points[i][1], points[i][0]]), {}, points[i][2]));
    }
}

function enableGPS(ids) {
    var markers = layers[1].getShapes();
    for (i in markers) {
        layers[0].add(markers[i]);
    }
    layers[1].clear();
    var markers = layers[0].getShapes();
    for (i in markers) {
        var marker = markers[i];
        if (ids.includes(marker.getId())) {
            layers[0].remove(marker);
            layers[1].add(marker);
        }
    }
}

function clearGPS() {
    layers[0].clear();
    layers[1].clear();
}

function enableMarker(id, active) {
    var markers = map.markers.getMarkers();
    for (i in markers) {
        var marker = markers[i];
        if (marker.metadata.id == id) {
            marker.setOptions({text: active ? 'red' : 'grey'});
            return;
        }
    }
}

function addMarker(id, lat, lng, active) {
    var marker = new atlas.HtmlMarker({
        anchor: 'top-left',
        draggable: true,
        htmlContent: '<img src="pin_{text}.png" />',
        pixelOffset: [-11, -35],
        position: [lng, lat],
        text: active ? 'red' : 'grey',
    });
    marker.metadata = {id: id};
    map.events.add('click', marker, markerClick);
    map.events.add('dragstart', marker, markerClick);
    map.events.add('drag', marker, markerDrag);
    map.events.add('dragend', marker, markerDragEnd);
    map.events.add('mouseover', marker, function () {
        map.getCanvasContainer().style.cursor = 'pointer';
    });
    map.events.add('mouseout', marker, function () {
        map.getCanvasContainer().style.cursor = 'grab';
    });
    map.markers.add(marker);
}

function markerClick(event) {
    var marker = event.target;
    python.marker_click(marker.metadata.id);
}

function markerDrag(event) {
    var marker = event.target;
    var pos = marker.getOptions().position;
    python.marker_drag(pos[1], pos[0]);
}

function markerDragEnd(event) {
    var marker = event.target;
    var pos = marker.getOptions().position;
    python.marker_drag_end(pos[1], pos[0], marker.metadata.id);
}

function markerDrop(x, y) {
    positions = map.pixelsToPositions([Pxl(x, y)]);
    python.marker_drop(positions[0][1], positions[0][0]);
}

function delMarker(id) {
    var markers = map.markers.getMarkers();
    for (i in markers) {
        var marker = markers[i];
        if (marker.metadata.id == id) {
            map.markers.remove(marker);
            return;
        }
    }
}
