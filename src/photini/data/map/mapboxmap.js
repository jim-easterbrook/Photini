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
 * It appears to be designed for something other than simple scripts so in
 * mapboxmap.py we define a variable 'exports' before the style switcher
 * script.
 */

var map;
var markers = {};
var gpsMarkers = {};
const padding = {top: 40, bottom: 5, left: 18, right: 18};
const noPadding = {top: 0, bottom: 0, left: 0, right: 0};


function loadMap(lat, lng, zoom, options) {
    options.center = [lng, lat];
    options.container = 'mapDiv';
    options.dragRotate = false;
    options.maxZoom = 19;
    options.style = 'mapbox://styles/mapbox/outdoors-v12';
    options.zoom = zoom - 1;
    map = new mapboxgl.Map(options);
    map.addControl(new exports.MapboxStyleSwitcherControl([
        {title: 'Street', uri: 'mapbox://styles/mapbox/streets-v12'},
        {title: 'Outdoors', uri: 'mapbox://styles/mapbox/outdoors-v12'},
        {title: 'Aerial', uri: 'mapbox://styles/mapbox/satellite-v9'},
    ], {defaultStyle: 'Outdoors'}));
    map.addControl(new mapboxgl.ScaleControl());
    map.addControl(new mapboxgl.NavigationControl({showCompass: false}));
    map.on('contextmenu', ignoreEvent);
    map.on('moveend', newBounds);
    map.on('zoomend', newBounds);
    python.initialize_finished();
    newBounds();
}

function ignoreEvent(event) {
}

function newBounds(event) {
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
        zoom: map.getZoom() + 1,
    });
}

function setView(lat, lng, zoom) {
    map.jumpTo({center: [lng, lat], padding: noPadding, zoom: zoom - 1});
}

function adjustBounds(north, east, south, west) {
    map.fitBounds(
        [west, south, east, north], {animate: true, padding: noPadding});
}

function fitPoints(points) {
    var bounds = mapboxgl.LngLatBounds.convert([
        [points[0][1], points[0][0]], [points[0][1], points[0][0]]]);
    for (i in points)
        bounds.extend([points[i][1], points[i][0]]);
    // Get viewport after setting padding
    map.setPadding(padding);
    const mapBounds = map.getBounds();
    const map_ne = mapBounds.getNorthEast();
    const map_sw = mapBounds.getSouthWest();
    var width = map_ne.lng - map_sw.lng;
    var height = map_ne.lat - map_sw.lat;
    const zoom = map.getZoom();
    // Get centre and zoom needed to fit points
    var options = map.cameraForBounds(bounds, {maxZoom: zoom});
    // Get pan needed
    const dx = Math.abs(options.center.lng - mapBounds.getCenter().lng);
    const dy = Math.abs(options.center.lat - mapBounds.getCenter().lat);
    if (options.zoom > zoom) {
        var scale = Math.pow(2, options.zoom - zoom);
        width *= scale;
        height *= scale;
    }
    if (dx > width * 10 || dy > height * 10) {
        // Long distance, go by air
        map.flyTo(options);
        return;
    }
    if (options.zoom == zoom && dx < width * 1.5 && dy < height * 1.5) {
        // Extend bounds to minimise pan
        var ne = bounds.getNorthEast();
        var sw = bounds.getSouthWest();
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
        options = map.cameraForBounds(bounds, {maxZoom: zoom});
    }
    map.easeTo(options);
}

function plotGPS(points) {
    for (i in points) {
        var icon = document.createElement("img");
        icon.src = 'circle_blue.png';
        icon.style.zIndex = '0';
        var marker = new mapboxgl.Marker({
            anchor: 'center',
            element: icon,
        });
        gpsMarkers[points[i][2]] = marker;
        marker.setLngLat([points[i][1], points[i][0]]);
        marker.addTo(map);
    }
}

function enableGPS(ids) {
    for (id in gpsMarkers) {
        var active = ids.includes(id);
        var icon = gpsMarkers[id].getElement();
        icon.src = active ? 'circle_red.png' : 'circle_blue.png';
        icon.style.zIndex = active ? '1' : '0';
    }
}

function clearGPS() {
    for (id in gpsMarkers)
        gpsMarkers[id].remove();
    gpsMarkers = {};
}

function enableMarker(id, active) {
    var icon = markers[id].getElement();
    icon.src = active ? 'pin_red.png' : 'pin_grey.png';
    icon.style.zIndex = active ? '3' : '2';
}

function addMarker(id, lat, lng, active) {
    var icon = document.createElement("img");
    icon.src = active ? 'pin_red.png' : 'pin_grey.png';
    icon.style.cursor = 'pointer';
    icon.style.zIndex = active ? '3' : '2';
    var marker = new mapboxgl.Marker({
        anchor: 'bottom',
        draggable: true,
        element: icon,
        offset: [1.5, 0],
    });
    marker.metadata = {id: id};
    markers[id] = marker;
    marker.setLngLat([lng, lat]);
    icon.addEventListener('click', markerClick);
    marker.on('dragstart', markerDragStart);
    marker.on('drag', markerDrag);
    marker.on('dragend', markerDragEnd);
    marker.addTo(map);
}

function markerClick() {
    for (id in markers)
        if (markers[id].getElement() == this) {
            python.marker_click(id);
            return;
        }
}

function markerDragStart() {
    python.marker_click(this.metadata.id);
}

function markerDrag() {
    var pos = this.getLngLat();
    python.marker_drag(pos.lat, pos.lng);
}

function markerDragEnd() {
    var pos = this.getLngLat();
    python.marker_drag_end(pos.lat, pos.lng, this.metadata.id);
}

function markerDrop(x, y) {
    var pos = map.unproject([x, y]);
    python.marker_drop(pos.lat, pos.lng);
}

function delMarker(id) {
    markers[id].remove();
    delete markers[id];
}
