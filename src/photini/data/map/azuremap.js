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
const gpsLayerId = ['gps_false', 'gps_true'];
var padding = {top: 40, bottom: 5, left: 18, right: 18};
var markers = {};
var markerIcon = ['', ''];

function loadMap(lat, lng, zoom, options) {
    if (!atlas.isSupported()) {
        console.error(
            'Azure maps is not supported, probably missing WebGL.');
        python.initialize_finished(false);
        return;
    } else if (!atlas.isSupported(true))
        console.warn(
            'Azure maps is supported, but may not perform well.');
    options.center = [lng, lat];
    options.dblClickZoomInteraction = false;
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
    // Set up GPS marker data layers
    for (const id of gpsLayerId) {
        const dataSource = new atlas.source.DataSource(id);
        map.sources.add(dataSource);
        map.layers.add(new atlas.layer.SymbolLayer(
            dataSource, id, {iconOptions: {
                allowOverlap: true,
                ignorePlacement: true,
                anchor: 'center',}}));
    }
    python.initialize_finished(true);
    newBounds();
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

function setIconData(pin, active, url, size) {
    if (pin) {
        markerIcon[active] = url;
        padding.left = 5 + ((size[0] * 3) / 7);
        padding.right = padding.left;
        padding.bottom = 5;
        padding.top = padding.bottom + size[1];
        const div = document.getElementById("mapDiv");
        const ltr = getComputedStyle(div).direction == 'ltr';
        if (ltr)
            padding.right += 110;
        else
            padding.left += 110;
    } else {
        const id = gpsLayerId[active];
        if (map.imageSprite.hasImage(id))
            map.imageSprite.remove(id);
        map.imageSprite.add(id, url).then(function () {
            const layer = map.layers.getLayerById(id);
            var options = layer.getOptions();
            options.iconOptions.image = id;
            layer.setOptions(options);
        });
    }
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
    if (new_zoom == camera.zoom &&
            BBox.containsPosition(mapBounds, BBox.getNorthEast(bounds)) &&
            BBox.containsPosition(mapBounds, BBox.getSouthWest(bounds)))
        return;
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
    const dataSource = map.sources.getById('gps_false');
    for (const point of points) {
        const geometry = new atlas.data.Point([point[1], point[0]]);
        const id = point[2];
        dataSource.add(new atlas.data.Feature(geometry, {}, id));
    }
}

function enableGPS(ids) {
    const dataTrue = map.sources.getById(gpsLayerId[1]);
    const dataFalse = map.sources.getById(gpsLayerId[0]);
    var promoted = [];
    for (const gpsMarker of dataFalse.getShapes())
        if (ids.includes(gpsMarker.getId()))
            promoted.push(gpsMarker);
    var demoted = [];
    for (const gpsMarker of dataTrue.getShapes())
        if (!ids.includes(gpsMarker.getId()))
            demoted.push(gpsMarker);
    dataTrue.add(promoted);
    dataFalse.remove(promoted);
    dataFalse.add(demoted);
    dataTrue.remove(demoted);
}

function clearGPS() {
    for (const id of gpsLayerId)
        map.sources.getById(id).clear();
}

function enableMarker(id, active) {
    var icon = markers[id].getElement();
    icon.src = markerIcon[active];
    icon.style.zIndex = active ? '1' : '0';
}

function addMarker(id, lat, lng, active) {
    var icon = document.createElement("img");
    icon.src = markerIcon[active];
    icon.style.cursor = 'pointer';
    icon.style.margin = '0px';
    icon.style.zIndex = active ? '1' : '0';
    var marker = new atlas.HtmlMarker({
        anchor: 'bottom',
        draggable: true,
        htmlContent: icon,
        pixelOffset: [0, 0],
        position: [lng, lat],
    });
    marker.id = id;
    markers[id] = marker;
    map.events.add('click', marker, markerClick);
    map.events.add('dragstart', marker, markerClick);
    map.events.add('drag', marker, markerDrag);
    map.events.add('dragend', marker, markerDragEnd);
    map.markers.add(marker);
}

function markerClick(event) {
    var marker = event.target;
    python.marker_click(marker.id);
}

function markerDrag(event) {
    var marker = event.target;
    var pos = marker.getOptions().position;
    python.marker_drag(pos[1], pos[0]);
}

function markerDragEnd(event) {
    var marker = event.target;
    var pos = marker.getOptions().position;
    python.marker_drag_end(pos[1], pos[0], marker.id);
}

function markerDrop(x, y) {
    pos = map.pixelsToPositions([Pxl(x, y)])[0];
    python.marker_drop(pos[1], pos[0]);
}

function delMarker(id) {
    map.markers.remove(markers[id]);
    delete markers[id];
}
