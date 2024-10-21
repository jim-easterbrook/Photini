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

var legacyMarkers = true;
var map;
var markers = {};
var markerIcon = ['', ''];
var gpsMarkers = {};
var gpsMarkerIcon = ['', ''];
const padding = {top: 40, bottom: 5, left: 18, right: 18};
const maxZoom = 20;

async function loadMap(lat, lng, zoom, options) {
    var mapOptions = {
        center: new google.maps.LatLng(lat, lng),
        controlSize: 30,
        disableDoubleClickZoom: true,
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
        zoomControl: true,
        zoomControlOptions: {
            position: google.maps.ControlPosition.INLINE_END_BLOCK_START,
        },
    };
    const div = document.getElementById("mapDiv");
    const { Map } = await google.maps.importLibrary("maps");
    map = new google.maps.Map(div, mapOptions);
    const mapCapabilities = map.getMapCapabilities();
    if (options.chrome_version >= 86
            && mapCapabilities.isAdvancedMarkersAvailable) {
        const { AdvancedMarkerElement } =
            await google.maps.importLibrary("marker");
        legacyMarkers = false;
    } else {
        console.warn(
            'Using legacy markers as advanced markers are not supported.');
    }
    google.maps.event.addListener(map, 'idle', newBounds);
    python.initialize_finished(true);
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
    const mapCentre = mapBounds.getCenter();
    const dx = Math.abs(normDx(boundsCentre.lng() - mapCentre.lng()));
    const dy = Math.abs(boundsCentre.lat() - mapCentre.lat());
    const pan = Math.max(dx / Math.max(boundsSpan.lng(), mapSpan.lng()),
                         dy / Math.max(boundsSpan.lat(), mapSpan.lat()));
    if (withPadding && newZoom >= maximumZoom && pan < 2) {
        map.panToBounds(bounds, padding);
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
        if (legacyMarkers)
            gpsMarkers[id] = new google.maps.Marker({
                map: map, position: latlng,
                icon: gpsMarkerIcon[0], zIndex: 2, clickable: false});
        else {
            var circle = document.createElement("img");
            circle.src = gpsMarkerIcon[0].src;
            circle.style.transform = gpsMarkerIcon[0].transform;
            gpsMarkers[id] = new google.maps.marker.AdvancedMarkerElement({
                map: map, position: latlng, content: circle, zIndex: 2});
        }
    }
}

function enableGPS(ids) {
    for (id in gpsMarkers) {
        const active = ids.includes(id) ? 1 : 0;
        const marker = gpsMarkers[id];
        if (legacyMarkers) {
            marker.setIcon(gpsMarkerIcon[active]);
            marker.setZIndex(active ? 3 : 2);
        }
        else {
            marker.content.src = gpsMarkerIcon[active].src;
            marker.zIndex = active ? 3 : 2;
        }
    }
}

function clearGPS() {
    for (id in gpsMarkers)
        gpsMarkers[id].setMap(null);
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
        // Ensure selected markers aren't hidden by type control
        if (getComputedStyle(div).direction == 'ltr')
            padding.right += 130;
        else
            padding.left += 130;
    } else if (legacyMarkers) {
        gpsMarkerIcon[active] = {
            anchor: new google.maps.Point(size[0] / 2, size[1] / 2),
            url: url};
    } else {
        var dy = 3 + (size[1] / 2);
        gpsMarkerIcon[active] = {
            src: url, transform: 'translate(0px,' + dy + 'px)'};
    }
}

function enableMarker(id, active) {
    var marker = markers[id];
    if (legacyMarkers) {
        marker.setIcon({url: markerIcon[active]});
        marker.setZIndex(active ? 1 : 0);
    }
    else {
        marker.content.src = markerIcon[active];
        marker.zIndex = active ? 1 : 0;
    }
}

function addMarker(id, lat, lng, active) {
    if (legacyMarkers) {
        var marker = new google.maps.Marker({
            icon: {url: markerIcon[active]},
            position: new google.maps.LatLng(lat, lng),
            map: map,
            draggable: true,
            crossOnDrag: false,
            zIndex: active ? 1 : 0,
        });
        google.maps.event.addListener(marker, 'click', markerClick);
        google.maps.event.addListener(marker, 'dblclick', markerClick);
        google.maps.event.addListener(marker, 'dragstart', markerClick);
        google.maps.event.addListener(marker, 'drag', markerDrag);
        google.maps.event.addListener(marker, 'dragend', markerDragEnd);
    }
    else {
        var icon = document.createElement("img");
        icon.src = markerIcon[active];
        icon.style.transform = 'translate(0px,3px)';
        var marker = new google.maps.marker.AdvancedMarkerElement({
            content: icon,
            position: new google.maps.LatLng(lat, lng),
            map: map,
            gmpDraggable: true,
            zIndex: active ? 1 : 0,
        });
        marker.addListener('click', markerClick);
        marker.addListener('dragstart', markerClick);
        marker.addListener('drag', markerDrag);
        marker.addListener('dragend', markerDragEnd);
    }
    marker.id = id;
    markers[id] = marker;
}

function markerClick(event) {
    python.marker_click(this.id);
}

function markerDrag(event) {
    python.marker_drag(event.latLng.lat(), event.latLng.lng());
}

function markerDragEnd(event) {
    python.marker_drag_end(event.latLng.lat(), event.latLng.lng(), this.id);
}

function markerDrop(x, y) {
    const projection = map.getProjection();
    const scale = Math.pow(2, -map.getZoom());
    // Get top left corner of map in Point coordinates
    const bounds = map.getBounds();
    const nw = projection.fromLatLngToPoint({
        lat: bounds.getNorthEast().lat(), lng: bounds.getSouthWest().lng()});
    // Get (lat, lng) from (x, y)
    const position = projection.fromPointToLatLng(
        new google.maps.Point(nw.x + (x * scale), nw.y + (y * scale)));
    python.marker_drop(position.lat(), position.lng());
}

function delMarker(id) {
    google.maps.event.clearInstanceListeners(markers[id]);
    markers[id].setMap(null);
    delete markers[id];
}
