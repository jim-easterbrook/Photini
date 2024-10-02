//  Photini - a simple photo metadata editor.
//  http://github.com/jim-easterbrook/Photini
//  Copyright (C) 2018-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
//
//  This program is free software: you can redistribute it and/or
//  modify it under the terms of the GNU General Public License as
//  published by the Free Software Foundation, either version 3 of the
//  License, or (at your option) any later version.
//
//  This program is distributed in the hope that it will be useful,
//  but WITHOUT ANY WARRANTY; without even the implied warranty of
//  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
//  General Public License for more details.
//
//  You should have received a copy of the GNU General Public License
//  along with this program.  If not, see
//  <http://www.gnu.org/licenses/>.

// See https://docs.mapbox.com/mapbox-gl-js/guides

/* The style switcher control is from https://github.com/el/style-switcher
 * It appears to be designed for something other than simple scripts so we
 * define a variable 'exports' before loading the style switcher script.
 */

var map;
var markers = {};
var markerIcon = ['', ''];
const gpsLayerId = ['gps_false', 'gps_true'];
var gpsMarkerIcon = ['', ''];
var gpsMarkers = {};
var lastZoom = 0;
const padding = {top: 40, bottom: 5, left: 18, right: 18};
const noPadding = {top: 0, bottom: 0, left: 0, right: 0};


function loadMap(lat, lng, zoom, options) {
    options.center = [lng, lat];
    options.container = 'mapDiv';
    options.doubleClickZoom = false;
    options.dragRotate = false;
    options.maxZoom = 19;
    options.minZoom = 0;
    options.projection = 'mercator';
    options.style = 'mapbox://styles/mapbox/outdoors-v12';
    options.zoom = zoom - 1;
    lastZoom = options.zoom;
    map = new mapboxgl.Map(options);
    const div = document.getElementById("mapDiv");
    const ltr = getComputedStyle(div).direction == 'ltr';
    map.addControl(new exports.MapboxStyleSwitcherControl([
        {title: 'Street', uri: 'mapbox://styles/mapbox/streets-v12'},
        {title: 'Outdoors', uri: 'mapbox://styles/mapbox/outdoors-v12'},
        {title: 'Aerial', uri: 'mapbox://styles/mapbox/satellite-v9'},], {defaultStyle: 'Outdoors'}), ltr ? 'top-right' : 'top-left');
    map.addControl(new mapboxgl.NavigationControl({showCompass: false}),
                   ltr ? 'top-right' : 'top-left');
    map.addControl(new mapboxgl.ScaleControl());
    map.on('contextmenu', ignoreEvent);
    map.on('moveend', newBounds);
    map.on('zoomend', newBounds);
    map.on('style.load', newStyle);
    map.on('load', doneLoading);
}

function doneLoading() {
    python.initialize_finished(true);
    newBounds();
}

function ignoreEvent(event) {
}

function newBounds(event) {
    lastZoom = map.getZoom();
    var centre = map.getCenter();
    // Adjust centre to allow for padding
    const pad = map.getPadding();
    centre = map.project(centre);
    centre = map.unproject([centre.x - ((pad.left - pad.right) / 2),
                            centre.y - ((pad.top - pad.bottom) / 2)]);
    const bounds = map.getBounds();
    const sw = bounds.getSouthWest();
    const ne = bounds.getNorthEast();
    python.new_status({
        centre: [centre.lat, centre.lng],
        bounds: [ne.lat, ne.lng, sw.lat, sw.lng],
        zoom: lastZoom + 1,
    });
}

function newStyle() {
    // Set up GPS marker data layers
    for (const id of gpsLayerId) {
        map.addSource(id, {
            type: 'geojson',
            dynamic: true,
            data: {type: 'FeatureCollection', features: []}
        });
        map.addLayer({
            id: id,
            type: 'symbol',
            layout: {'icon-image': id, 'icon-allow-overlap': true},
            source: id,
        });
    }
    var features = [[], []];
    for (id in gpsMarkers)
        features[gpsMarkers[id].active].push({
            id: id, type: 'Feature', geometry: gpsMarkers[id].geometry});
    for (active in features) {
        updateGPSMarkerImage(active);
        map.getSource(gpsLayerId[active]).setData({
            type: 'FeatureCollection', features: features[active]});
    }
}

function setView(lat, lng, zoom) {
    lastZoom = zoom - 1;
    map.jumpTo({center: [lng, lat], padding: noPadding, zoom: lastZoom});
}

function moveTo(bounds, withPadding, maxZoom) {
    var ne = bounds.getNorthEast();
    var sw = bounds.getSouthWest();
    // Set padding if needed
    const oldPadding = map.getPadding();
    const newPadding = withPadding ? padding : noPadding;
    if (oldPadding.top != newPadding.top ||
            oldPadding.bottom != newPadding.bottom ||
            oldPadding.left != newPadding.left ||
            oldPadding.right != newPadding.right) {
        // Move centre to allow for padding change
        var x_shift = ((newPadding.left - newPadding.right) -
                       (oldPadding.left - oldPadding.right)) / 2;
        var y_shift = ((newPadding.top - newPadding.bottom) -
                       (oldPadding.top - oldPadding.bottom)) / 2;
        var centre = map.getCenter();
        centre = map.project(centre);
        centre = map.unproject([centre.x + x_shift, centre.y + y_shift]);
        map.jumpTo({center: centre, padding: newPadding});
    }
    // Get viewport after setting padding
    const mapBounds = map.getBounds();
    const map_ne = mapBounds.getNorthEast();
    const map_sw = mapBounds.getSouthWest();
    var width = map_ne.lng - map_sw.lng;
    var height = map_ne.lat - map_sw.lat;
    // Get centre and zoom needed to fit points
    var options = map.cameraForBounds(bounds, {maxZoom: maxZoom});
    // Get pan needed
    var dx = options.center.lng - mapBounds.getCenter().lng;
    if (dx > 180) {
        dx -= 360;
        bounds = mapboxgl.LngLatBounds.convert([
            [sw.lng - 360, sw.lat], [ne.lng - 360, ne.lat]]);
        ne = bounds.getNorthEast();
        sw = bounds.getSouthWest();
        options = map.cameraForBounds(bounds, {maxZoom: maxZoom});
    }
    else if (dx < -180) {
        dx += 360;
        bounds = mapboxgl.LngLatBounds.convert([
            [sw.lng + 360, sw.lat], [ne.lng + 360, ne.lat]]);
        ne = bounds.getNorthEast();
        sw = bounds.getSouthWest();
        options = map.cameraForBounds(bounds, {maxZoom: maxZoom});
    }
    dx = Math.abs(dx)
    const dy = Math.abs(options.center.lat - mapBounds.getCenter().lat);
    // Compute normalised pan needed
    const pan = Math.max(dx / Math.max(ne.lng - sw.lng, width),
                         dy / Math.max(ne.lat - sw.lat, height));
    const zoom = map.getZoom();
    if (pan > 10 || Math.abs(options.zoom - zoom) > 2) {
        // Long distance, go by air
        lastZoom = options.zoom;
        map.flyTo(options);
        return;
    }
    if (withPadding && options.zoom == zoom && pan < 2) {
        // Extend bounds to minimise pan
        if (ne.lng > map_ne.lng)
            bounds.extend([ne.lng - width, ne.lat]);
        else if (sw.lng < map_sw.lng)
            bounds.extend([sw.lng + width, sw.lat]);
        else {
            bounds.extend([map_ne.lng, ne.lat]);
            bounds.extend([map_sw.lng, sw.lat]);
        }
        if (ne.lat > map_ne.lat)
            bounds.extend([ne.lng, ne.lat - height]);
        else if (sw.lat < map_sw.lat)
            bounds.extend([sw.lng, sw.lat + height]);
        else {
            bounds.extend([ne.lng, map_ne.lat]);
            bounds.extend([sw.lng, map_sw.lat]);
        }
        options = map.cameraForBounds(bounds, {maxZoom: maxZoom});
        options.zoom = zoom;
    }
    lastZoom = options.zoom;
    if (options.zoom == zoom &&
            mapBounds.contains(bounds.getNorthEast()) &&
            mapBounds.contains(bounds.getSouthWest()))
        return;
    map.easeTo(options);
}

function adjustBounds(north, east, south, west) {
    if (east < west)
        // Spanning 180 degree meridian
        east += 360;
    moveTo(mapboxgl.LngLatBounds.convert([[west, south], [east, north]]),
           false, map.getMaxZoom() - 3);
}

function fitPoints(points) {
    var bounds = mapboxgl.LngLatBounds.convert([
        [points[0][1], points[0][0]], [points[0][1], points[0][0]]]);
    for (const point of points) {
        var lng = point[1];
        if (bounds.getEast() - lng > 180)
            lng += 360;
        else if (lng - bounds.getWest() > 180)
            lng -= 360;
        bounds.extend([lng, point[0]]);
    }
    moveTo(bounds, true, lastZoom);
}

function plotGPS(points) {
    var features = [];
    for (const point of points) {
        const id = point[2];
        gpsMarkers[id] = {
            active: 0,
            geometry: {type: 'Point', coordinates: [point[1], point[0]]}
        }
        features.push({
            id: id, type: 'Feature', geometry: gpsMarkers[id].geometry});
    }
    map.getSource(gpsLayerId[0]).updateData({
        type: 'FeatureCollection',
        features: features,
    });
}

function enableGPS(ids) {
    var updates = [[],[]];
    for (id in gpsMarkers) {
        const active = ids.includes(id) ? 1 : 0;
        if (gpsMarkers[id].active != active) {
            updates[active].push({
                id: id, type: 'Feature', geometry: gpsMarkers[id].geometry});
            updates[1-active].push({
                id: id, type: 'Feature', geometry: null});
            gpsMarkers[id].active = active;
        }
    }
    for (active in gpsLayerId)
        map.getSource(gpsLayerId[active]).updateData({
            type: 'FeatureCollection', features: updates[active]});
}

function clearGPS() {
    for (const id of gpsLayerId)
        map.getSource(id).setData({
            type: 'FeatureCollection', features: []});
    gpsMarkers = {};
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
            padding.right += 40;
        else
            padding.left += 40;
    } else {
        gpsMarkerIcon[active] = url;
        updateGPSMarkerImage(active);
    }
}

function updateGPSMarkerImage(active) {
    if (!gpsMarkerIcon[active]) return;
    const id = gpsLayerId[active];
    map.loadImage(gpsMarkerIcon[active], (error, image) => {
        if (error) throw error;
        if (map.hasImage(id))
            map.updateImage(id, image);
        else
            map.addImage(id, image);
    });
}

function enableMarker(id, active) {
    var icon = markers[id].getElement();
    icon.src = markerIcon[active];
    icon.style.zIndex = active ? '2' : '1';
}

function addMarker(id, lat, lng, active) {
    var icon = document.createElement("img");
    icon.src = markerIcon[active];
    icon.style.cursor = 'pointer';
    icon.style.zIndex = active ? '2' : '1';
    icon.id = id;
    var marker = new mapboxgl.Marker({
        anchor: 'bottom',
        draggable: true,
        element: icon,
        offset: [0, 0],
    });
    marker.id = id;
    markers[id] = marker;
    marker.setLngLat([lng, lat]);
    icon.addEventListener('click', markerClick);
    marker.on('dragstart', markerClick);
    marker.on('drag', markerDrag);
    marker.on('dragend', markerDragEnd);
    marker.addTo(map);
}

function markerClick(event) {
    python.marker_click(this.id);
}

function markerDrag() {
    var pos = this.getLngLat();
    python.marker_drag(pos.lat, pos.lng);
}

function markerDragEnd() {
    var pos = this.getLngLat();
    python.marker_drag_end(pos.lat, pos.lng, this.id);
}

function markerDrop(x, y) {
    var pos = map.unproject([x, y]);
    python.marker_drop(pos.lat, pos.lng);
}

function delMarker(id) {
    markers[id].remove();
    delete markers[id];
}
