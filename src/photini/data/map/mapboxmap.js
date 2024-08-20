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
var lastZoom = 0;
const padding = {top: 40, bottom: 5, left: 18, right: 18};
const noPadding = {top: 0, bottom: 0, left: 0, right: 0};


function loadMap(lat, lng, zoom, options) {
    options.center = [lng, lat];
    options.container = 'mapDiv';
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
    if (ltr)
        padding.right += 40;
    else
        padding.left += 40;
    map.addControl(new exports.MapboxStyleSwitcherControl([
        {title: 'Street', uri: 'mapbox://styles/mapbox/streets-v12'},
        {title: 'Outdoors', uri: 'mapbox://styles/mapbox/outdoors-v12'},
        {title: 'Aerial', uri: 'mapbox://styles/mapbox/satellite-v9'},
    ], {defaultStyle: 'Outdoors'}), ltr ? 'top-right' : 'top-left');
    map.addControl(new mapboxgl.NavigationControl({showCompass: false}),
                   ltr ? 'top-right' : 'top-left');
    map.addControl(new mapboxgl.ScaleControl());
    map.on('contextmenu', ignoreEvent);
    map.on('moveend', newBounds);
    map.on('zoomend', newBounds);
    python.initialize_finished();
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
                         dy / Math.max(ne.lat - ne.lng, height));
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
    for (i in points) {
        var lng = points[i][1];
        if (bounds.getEast() - lng > 180)
            lng += 360;
        else if (lng - bounds.getWest() > 180)
            lng -= 360;
        bounds.extend([lng, points[i][0]]);
    }
    moveTo(bounds, true, lastZoom);
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
