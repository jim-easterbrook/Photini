//  Photini - a simple photo metadata editor.
//  http://github.com/jim-easterbrook/Photini
//  Copyright (C) 2012-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

// See https://developers.google.com/maps/documentation/javascript/reference

var map;
var markers = {};
var gpsMarkers = {};
const padding = {top: 40, bottom: 5, left: 18, right: 18};
const maxZoom = 20;
if (use_old_markers) {
    var icon_on;
    var icon_off;
    var gpsBlueCircle;
    var gpsRedCircle;
}

function loadMap(lat, lng, zoom, options) {
    var mapOptions = {
        center: new google.maps.LatLng(lat, lng),
        fullscreenControl: false,
        scaleControl: true,
        streetViewControl: false,
        tilt: 0,
        zoom: zoom,
        maxZoom: maxZoom,
        minZoom: 1,
        isFractionalZoomEnabled: true,
        mapId: "ce7cafb5b0de6e31",
        mapTypeId: google.maps.MapTypeId.ROADMAP,
        mapTypeControl: true,
        mapTypeControlOptions: {
            position: google.maps.ControlPosition.BLOCK_START_INLINE_END,
            style: google.maps.MapTypeControlStyle.DROPDOWN_MENU,
        },
    };
    map = new google.maps.Map(document.getElementById("mapDiv"), mapOptions);
    google.maps.event.addListener(map, 'idle', newBounds);
    if (use_old_markers) {
        var anchor = new google.maps.Point(11, 35);
        icon_on = {anchor: anchor, url: 'pin_red.png'};
        icon_off = {anchor: anchor, url: 'pin_grey.png'};
        anchor = new google.maps.Point(5, 5);
        gpsBlueCircle = {anchor: anchor, url: 'circle_blue.png'};
        gpsRedCircle = {anchor: anchor, url: 'circle_red.png'};
    }
    python.initialize_finished();
}

function newBounds() {
    const centre = map.getCenter();
    const bounds = map.getBounds();
    const sw = bounds.getSouthWest();
    const ne = bounds.getNorthEast();
    python.new_status({
        centre: [centre.lat(), centre.lng()],
        bounds: [ne.lat(), ne.lng(), sw.lat(), sw.lng()],
        zoom: map.getZoom(),
    });
}

function setView(lat, lng, zoom) {
    map.setZoom(zoom)
    map.panTo(new google.maps.LatLng(lat, lng));
}

function normDx(dx) {
    if (dx > 180)
        return dx - 360;
    if (dx < -180)
        return dx + 360;
    return dx;
}

function moveTo(bounds, withPadding, maximumZoom) {
    const zoom = map.getZoom();
    // Get map viewport
    var mapBounds = map.getBounds();
    if (withPadding) {
        // Reduce map bounds to allow for padding
        const projection = map.getProjection();
        const scale = Math.pow(2, -zoom);
        var sw = projection.fromLatLngToPoint(mapBounds.getSouthWest());
        var ne = projection.fromLatLngToPoint(mapBounds.getNorthEast());
        sw = projection.fromPointToLatLng(new google.maps.Point(
            sw.x + (padding.left * scale), sw.y - (padding.bottom * scale)));
        ne = projection.fromPointToLatLng(new google.maps.Point(
            ne.x - (padding.right * scale), ne.y + (padding.top * scale)));
        mapBounds = new google.maps.LatLngBounds(sw, ne);
    }
    // Get map and bounds dimensions
    const boundsSpan = bounds.toSpan();
    const mapSpan = mapBounds.toSpan();
    var newZoom = zoom - Math.log2(Math.max(1.0e-30,
        boundsSpan.lng() / mapSpan.lng(), boundsSpan.lat() / mapSpan.lat()));
    if (newZoom < zoom) {
        // Zoom out to fit bounds
        map.fitBounds(bounds, withPadding ? padding : 0);
        return;
    }
    // Compute normalised pan needed
    const boundsCentre = bounds.getCenter();
    const mapCentre = map.getCenter();
    const dx = Math.abs(normDx(boundsCentre.lng() - mapCentre.lng()));
    const dy = Math.abs(boundsCentre.lat() - mapCentre.lat());
    const pan = Math.max(dx / Math.max(boundsSpan.lng(), mapSpan.lng()),
                         dy / Math.max(boundsSpan.lat(), mapSpan.lat()));
    if (withPadding && newZoom >= maximumZoom && pan < 2) {
        map.panToBounds(bounds, withPadding ? padding : 0);
        return;
    }
    map.setOptions({maxZoom: maximumZoom});
    map.fitBounds(bounds, withPadding ? padding : 0);
    map.setOptions({maxZoom: maxZoom});
}

function adjustBounds(north, east, south, west) {
    moveTo(new google.maps.LatLngBounds({
        north: north, east: east, south: south, west: west}),
        false, maxZoom - 3);
}

function fitPoints(points) {
    var bounds = new google.maps.LatLngBounds();
    for (i in points)
        bounds.extend({lat: points[i][0], lng: points[i][1]});
    moveTo(bounds, true, map.getZoom());
}

function plotGPS(points) {
    for (i in points) {
        const latlng = new google.maps.LatLng(points[i][0], points[i][1]);
        const id = points[i][2];
        if (use_old_markers)
            gpsMarkers[id] = new google.maps.Marker({
                map: map, position: latlng,
                icon: gpsBlueCircle, zIndex: 2, clickable: false});
        else {
            var circle = document.createElement("img");
            circle.src = 'circle_blue.png';
            circle.style.transform = 'translate(0.5px,8.5px)';
            gpsMarkers[id] = new google.maps.marker.AdvancedMarkerElement({
                map: map, position: latlng, content: circle, zIndex: 2});
        }
    }
}

function enableGPS(ids) {
    for (id in gpsMarkers)
        if (use_old_markers) {
            if (ids.includes(id))
                gpsMarkers[id].setOptions({icon: gpsRedCircle, zIndex: 3});
            else
                gpsMarkers[id].setOptions({icon: gpsBlueCircle, zIndex: 2});
        }
        else {
            gpsMarkers[id].content.src =
                ids.includes(id) ? 'circle_red.png' : 'circle_blue.png';
            gpsMarkers[id].zIndex = ids.includes(id) ? 3 : 2;
        }
}

function clearGPS() {
    for (id in gpsMarkers)
        gpsMarkers[id].setMap(null);
    gpsMarkers = {};
}

function enableMarker(id, active) {
    var marker = markers[id];
    if (use_old_markers) {
        if (active)
            marker.setOptions({icon: icon_on, zIndex: 1});
        else
            marker.setOptions({icon: icon_off, zIndex: 0});
    }
    else {
        marker.content.src = active ? 'pin_red.png' : 'pin_grey.png';
        marker.zIndex = active ? 1 : 0;
    }
}

function addMarker(id, lat, lng, active) {
    if (use_old_markers) {
        var marker = new google.maps.Marker({
            icon: icon_off,
            position: new google.maps.LatLng(lat, lng),
            map: map,
            draggable: true,
            crossOnDrag: false,
        });
    }
    else {
        var icon = document.createElement("img");
        icon.src = 'pin_grey.png';
        icon.style.transform = 'translate(1.5px,3px)';
        var marker = new google.maps.marker.AdvancedMarkerElement({
            content: icon,
            position: new google.maps.LatLng(lat, lng),
            map: map,
            gmpDraggable: true,
        });
    }
    markers[id] = marker;
    google.maps.event.addListener(marker, 'click', markerClick);
    google.maps.event.addListener(marker, 'dragstart', markerClick);
    google.maps.event.addListener(marker, 'drag', markerDrag);
    google.maps.event.addListener(marker, 'dragend', markerDragEnd);
    enableMarker(id, active)
}

function markerToId(marker) {
    for (id in markers)
        if (markers[id] == marker)
            return id;
}

function markerClick(event) {
    python.marker_click(markerToId(this));
}

function markerDrag(event) {
    var loc = event.latLng;
    python.marker_drag(loc.lat(), loc.lng());
}

function markerDragEnd(event) {
    var loc = event.latLng;
    python.marker_drag_end(loc.lat(), loc.lng(), markerToId(this));
}

function markerDrop(x, y) {
    // convert x, y to world coordinates
    var scale = Math.pow(2, map.getZoom());
    var nw = new google.maps.LatLng(
        map.getBounds().getNorthEast().lat(),
        map.getBounds().getSouthWest().lng()
        );
    var worldCoordinateNW = map.getProjection().fromLatLngToPoint(nw);
    var worldX = worldCoordinateNW.x + (x / scale);
    var worldY = worldCoordinateNW.y + (y / scale);
    // convert world coordinates to lat & lng
    var position = map.getProjection().fromPointToLatLng(
        new google.maps.Point(worldX, worldY));
    python.marker_drop(position.lat(), position.lng());
}

function delMarker(id) {
    google.maps.event.clearInstanceListeners(markers[id]);
    markers[id].setMap(null);
    delete markers[id];
}
