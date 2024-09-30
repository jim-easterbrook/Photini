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

// See https://docs.mapbox.com/mapbox.js/api/v3.3.1/
// and https://leafletjs.com/reference-1.7.1.html

var drag_id = -1;
var map;
var markers = {};
var markerIcon = ['', ''];
var gpsMarkers = {};
var gpsMarkerIcon = ['', ''];


function loadMap(lat, lng, zoom, options) {
    L.mapbox.accessToken = options.accessToken;
    var baseMaps = {
        "Street"  : L.mapbox.styleLayer(
            'mapbox://styles/mapbox/streets-v12',
            {tileSize: 512, zoomOffset: -1}),
        "Outdoors": L.mapbox.styleLayer(
            'mapbox://styles/mapbox/outdoors-v12',
            {tileSize: 512, zoomOffset: -1}),
        "Aerial"  :  L.mapbox.styleLayer(
            'mapbox://styles/mapbox/satellite-v9',
            {tileSize: 512, zoomOffset: -1}),
    };
    map = L.mapbox.map(document.getElementById("mapDiv"));
    map.doubleClickZoom.disable();
    // Map vanishes if zoomed too much
    map.setMaxZoom(18);
    map.setView([lat, lng], zoom);
    baseMaps["Outdoors"].addTo(map);
    L.control.layers(baseMaps).addTo(map);
    L.control.scale().addTo(map);
    map.on('contextmenu', ignoreEvent);
    map.on('moveend zoomend', newBounds);
    python.new_status({version: L.version});
    python.initialize_finished(true);
    newBounds();
}

function ignoreEvent(event) {
}

function newBounds(event) {
    var centre = map.getCenter();
    var bounds = map.getBounds();
    var sw = bounds.getSouthWest();
    var ne = bounds.getNorthEast();
    python.new_status({
        centre: [centre.lat, centre.lng],
        bounds: [ne.lat, ne.lng, sw.lat, sw.lng],
        zoom: map.getZoom(),
        });
}

function setView(lat, lng, zoom) {
    map.setView([lat, lng], zoom, {animate: true});
}

function adjustBounds(north, east, south, west) {
    map.fitBounds([[north, east], [south, west]], {animate: true});
}

function fitPoints(points) {
    var bounds = L.latLngBounds(points);
    if (map.getBounds().contains(bounds))
        return;
    map.fitBounds(bounds, {
        paddingTopLeft: [15, 50], paddingBottomRight: [15, 10],
        maxZoom: map.getZoom(), animate: true});
}

function plotGPS(points) {
    for (var i = 0; i < points.length; i++) {
        var latlng = L.latLng(points[i][0], points[i][1]);
        var id = points[i][2];
        gpsMarkers[id] = L.marker(latlng, {
            icon: gpsMarkerIcon[0], interactive: false, zIndexOffset: 1001});
        gpsMarkers[id].addTo(map);
    }
}

function enableGPS(ids) {
    for (var id in gpsMarkers) {
        var marker = gpsMarkers[id];
        var active = ids.includes(id) ? 1 : 0;
        marker.setZIndexOffset(active ? 1002 : 1001);
        marker.setIcon(gpsMarkerIcon[active]);
    }
}

function clearGPS() {
    for (var id in gpsMarkers)
        gpsMarkers[id].remove();
    gpsMarkers = {};
}

function setIconData(pin, active, url, size) {
    if (pin) {
        markerIcon[active] = new L.Icon({
            iconUrl: url,
            iconSize: size,
            iconAnchor: [size[0] / 2, size[1]]});
    } else {
        gpsMarkerIcon[active] = new L.Icon({
            iconUrl: url,
            iconSize: size,
            iconAnchor: [size[0] / 2, size[1] / 2]});
    }
}

function enableMarker(id, active) {
    var marker = markers[id];
    if (id != drag_id || !active)
        marker.setIcon(markerIcon[active]);
    marker.setZIndexOffset(active ? 1000 : 0);
}

function addMarker(id, lat, lng, active) {
    var marker = L.marker([lat, lng], {draggable: true, autoPan: true});
    marker.addTo(map);
    markers[id] = marker;
    marker.on('click', markerClick);
    marker.on('dragstart', markerDragStart);
    marker.on('drag', markerDrag);
    marker.on('dragend', markerDragEnd);
    enableMarker(id, active)
}

function markerToId(marker) {
    for (var id in markers)
        if (markers[id] == marker)
            return id;
}

function markerClick(event) {
    python.marker_click(markerToId(this));
}

function markerDragStart(event) {
    // workaround for Leaflet bug #4484 - don't change marker image until end
    // of drag. https://github.com/Leaflet/Leaflet/issues/4484
    var id = markerToId(this);
    drag_id = id;
    python.marker_click(id);
}

function markerDrag(event) {
    var loc = this.getLatLng();
    python.marker_drag(loc.lat, loc.lng);
}

function markerDragEnd(event) {
    var loc = this.getLatLng();
    var id = markerToId(this);
    this.setIcon(markerIcon[1]);
    python.marker_drag_end(loc.lat, loc.lng, id);
    drag_id = -1;
}

function markerDrop(x, y) {
    var position = map.containerPointToLatLng([x, y]);
    python.marker_drop(position.lat, position.lng);
}

function delMarker(id) {
    map.removeLayer(markers[id]);
    delete markers[id];
}
