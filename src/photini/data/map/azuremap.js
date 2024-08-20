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
var lastCamera = {};
var layers = [];
var padding = {top: 40, bottom: 5, left: 18, right: 18};

function loadMap(lat, lng, zoom, options) {
    options.center = [lng, lat];
    options.dragRotateInteraction = false;
    options.maxZoom = 19;
    options.minZoom = 1;
    options.zoom = zoom - 1;
    map = new atlas.Map("mapDiv", options);
    //Wait until the map resources are ready.
    map.events.add('ready', mapReady);
}

function mapReady() {
    const div = document.getElementById("mapDiv");
    const ltr = getComputedStyle(div).direction == 'ltr';
    if (ltr)
        padding.right += 110;
    else
        padding.left += 110;
    map.controls.add(
        [new atlas.control.StyleControl({
            mapStyles: ['road', 'road_shaded_relief',
                        'satellite', 'satellite_road_labels'],
            layout: 'list'}),
         new atlas.control.ZoomControl()],
        {position: ltr ? 'top-right' : 'top-left'});
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

function newBounds() {
    lastCamera = map.getCamera();
    const bounds = lastCamera.bounds;
    python.new_status({
        centre: [lastCamera.center[1], lastCamera.center[0]],
        bounds: [BBox.getNorth(bounds), BBox.getEast(bounds),
                 BBox.getSouth(bounds), BBox.getWest(bounds)],
        zoom: lastCamera.zoom + 1,
        });
}

function setView(lat, lng, zoom) {
    map.setCamera({center: [lng, lat], zoom: zoom - 1});
}

function normDx(dx) {
    if (dx > 180)
        return dx - 360;
    if (dx < -180)
        return dx + 360;
    return dx;
}

function moveTo(bounds, withPadding, maxZoom) {
    const camera = map.getCamera();
    var mapBounds = lastCamera.bounds;
    if (withPadding) {
        // Reduce map bounds to allow for padding
        var positions = [
            BBox.getNorthEast(mapBounds), BBox.getSouthWest(mapBounds)];
        var pixels = atlas.math.mercatorPositionsToPixels(
            positions, lastCamera.zoom);
        pixels = [Pxl(Pxl.getX(pixels[0]) - padding.right,
                      Pxl.getY(pixels[0]) + padding.top),
                  Pxl(Pxl.getX(pixels[1]) + padding.left,
                      Pxl.getY(pixels[1]) - padding.bottom)];
        positions = atlas.math.mercatorPixelsToPositions(
            pixels, lastCamera.zoom);
        mapBounds = BBox.fromPositions(positions);
    }
    // Get map and bounds dimensions
    var map_h = BBox.getHeight(mapBounds);
    var map_w = BBox.getWidth(mapBounds);
    var bounds_h = BBox.getHeight(bounds);
    var bounds_w = BBox.getWidth(bounds);
    // Compute normalised pan needed
    const boundsCentre = BBox.getCenter(bounds);
    // If map is mid flight, use current position to determine pan needed
    const mapCentre = BBox.getCenter(camera.bounds);
    var dx = normDx(boundsCentre[0] - mapCentre[0]);
    var dy = boundsCentre[1] - mapCentre[1];
    const pan = Math.max(Math.abs(dx) / Math.max(bounds_w, map_w),
                         Math.abs(dy) / Math.max(bounds_h, map_h));
    // Jump, pan or zoom out?
    var options = {};
    var new_zoom = lastCamera.zoom - Math.log2(
        Math.max(1.0e-30, bounds_h / map_h, bounds_w / map_w));
    if (new_zoom < lastCamera.zoom) {
        // Zoom out to fit bounds
        options = {bounds: bounds};
        if (withPadding)
            options.padding = padding;
    }
    else {
        new_zoom = Math.min(new_zoom, maxZoom);
        if (withPadding && new_zoom == maxZoom && pan < 1.5) {
            // Extend bounds to minimise pan
            var west = BBox.getWest(bounds);
            var south = BBox.getSouth(bounds);
            var east = BBox.getEast(bounds);
            var north = BBox.getNorth(bounds);
            if (east > BBox.getEast(mapBounds))
                west = Math.min(west, east - map_w);
            else if (west < BBox.getWest(mapBounds))
                east = Math.max(east, west + map_w);
            else {
                west = BBox.getWest(mapBounds);
                east = BBox.getEast(mapBounds);
            }
            if (north > BBox.getNorth(mapBounds))
                south = Math.min(south, north - map_h);
            else if (south < BBox.getSouth(mapBounds))
                north = Math.max(north, south + map_h);
            else {
                south = BBox.getSouth(mapBounds);
                north = BBox.getNorth(mapBounds);
            }
            bounds = BBox([west, south, east, north])
            options = {bounds: bounds, padding: padding};
        }
        else
            options = {center: BBox.getCenter(bounds), zoom: new_zoom};
    }
    if (pan > 10 || Math.abs(new_zoom - camera.zoom) > 2) {
        // Long distance, go by air
        options.type = 'fly';
        options.duration = Math.max(
            500, Math.log(Math.max(pan, 0.1)) * 1000,
            Math.abs(new_zoom - camera.zoom) * 400);
    }
    else {
        options.type = 'ease';
        options.duration = Math.min(500, pan * 200);
    }
    map.setCamera(options);
}

function adjustBounds(north, east, south, west) {
    moveTo([west, south, east, north], false, map.getCamera().maxZoom - 3);
}

function fitPoints(points) {
    moveTo(BBox.fromPositions(Pos.fromLatLngs(points)),
           true, lastCamera.zoom);
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
