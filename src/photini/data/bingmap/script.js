//  Photini - a simple photo metadata editor.
//  http://github.com/jim-easterbrook/Photini
//  Copyright (C) 2012-21  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

// See https://docs.microsoft.com/en-us/bingmaps/v8-web-control/map-control-api/

var map;
var layers = [];

function loadMap(lat, lng, zoom)
{
    var mapOptions = {
        center: new Microsoft.Maps.Location(lat, lng),
        zoom: zoom,
        mapTypeId: Microsoft.Maps.MapTypeId.road,
        disableBirdseye: true,
        disableStreetside: true,
        enableSearchLogo: false,
        showLocateMeButton: false,
        maxZoom: 20,
        navigationBarMode: Microsoft.Maps.NavigationBarMode.compact,
        navigationBarOrientation: Microsoft.Maps.NavigationBarOrientation.vertical,
        };
    map = new Microsoft.Maps.Map("#mapDiv", mapOptions);
    for (var i = 0; i < 4; i++)
    {
        layers.push(new Microsoft.Maps.Layer());
        map.layers.insert(layers[i]);
    }
    Microsoft.Maps.loadModule('Microsoft.Maps.SpatialMath');
    Microsoft.Maps.Events.addHandler(layers[0], 'click', markerClick);
    Microsoft.Maps.Events.addHandler(layers[1], 'click', markerClick);
    Microsoft.Maps.Events.addHandler(map, 'viewchangeend', newBounds);
    map.getCredentials(newCredentials);
}

function newCredentials(sessionId)
{
    python.new_status({
        session_id: sessionId,
        });
    python.initialize_finished();
}

function newBounds()
{
    var centre = map.getCenter();
    var bounds = map.getBounds();
    python.new_status({
        centre: [centre.latitude, centre.longitude],
        bounds: [bounds.getNorth(), bounds.getEast(),
                 bounds.getSouth(), bounds.getWest()],
        zoom: map.getZoom(),
        });
}

function setView(lat, lng, zoom)
{
    map.setView({center: new Microsoft.Maps.Location(lat, lng), zoom: zoom});
}

function adjustBounds(north, east, south, west)
{
    var bounds = Microsoft.Maps.LocationRect.fromEdges(north, west, south, east);
    map.setView({bounds: bounds});
}

function fitPoints(points)
{
    var locations = [];
    for (var i = 0; i < points.length; i++)
        locations.push(new Microsoft.Maps.Location(points[i][0], points[i][1]));
    var bounds = Microsoft.Maps.LocationRect.fromLocations(locations);
    var mapBounds = map.getBounds();
    var nw = bounds.getNorthwest();
    var se = bounds.getSoutheast();
    nw = new Microsoft.Maps.Location(nw.latitude + (mapBounds.height * 0.13),
                                     nw.longitude - (mapBounds.width * 0.04));
    se = new Microsoft.Maps.Location(se.latitude - (mapBounds.height * 0.04),
                                     se.longitude + (mapBounds.width * 0.04));
    if (mapBounds.contains(nw) && mapBounds.contains(se))
        return;
    bounds = Microsoft.Maps.LocationRect.fromCorners(nw, se);
    if (bounds.height > mapBounds.height || bounds.width > mapBounds.width)
    {
        map.setView({bounds: bounds});
        return;
    }
    var d_lat = Math.max(nw.latitude - mapBounds.getNorth(), 0) +
                Math.min(se.latitude - mapBounds.getSouth(), 0);
    var d_long = Math.min(nw.longitude - mapBounds.getWest(), 0) +
                 Math.max(se.longitude - mapBounds.getEast(), 0);
    if (d_lat < mapBounds.height / 2 && d_long < mapBounds.width / 2)
        map.setView({center: new Microsoft.Maps.Location(
            mapBounds.center.latitude + d_lat,
            mapBounds.center.longitude + d_long)});
    else
        map.setView({center: bounds.center});
}

function plotGPS(points)
{
    for (var i = 0; i < points.length; i++)
    {
        var latlng = new Microsoft.Maps.Location(points[i][0], points[i][1]);
        var id = points[i][2];
        var marker = new Microsoft.Maps.Pushpin(latlng, {
            icon: '../map_circle_blue.png',
            anchor: new Microsoft.Maps.Point(5, 5)});
        marker.metadata = {id: id};
        layers[2].add(marker);
    }
}

function enableGPS(ids)
{
    var markers = layers[3].getPrimitives();
    for (var i = 0; i < markers.length; i++)
    {
        var marker = markers[i];
        marker.setOptions({icon: '../map_circle_blue.png'});
        layers[2].add(marker);
    }
    layers[3].clear();
    var markers = layers[2].getPrimitives();
    for (var i = 0; i < markers.length; i++)
    {
        var marker = markers[i];
        if (ids.includes(marker.metadata.id))
        {
            layers[2].remove(marker);
            marker.setOptions({icon: '../map_circle_red.png'});
            layers[3].add(marker);
        }
    }
}

function clearGPS()
{
    layers[2].clear();
    layers[3].clear();
}

function adjustMarker(id, fromLayer, toLayer, icon)
{
    var markers = fromLayer.getPrimitives();
    for (var i = 0; i < markers.length; i++)
    {
        var marker = markers[i];
        if (marker.metadata.id == id)
        {
            fromLayer.remove(marker);
            marker.setOptions({icon: icon});
            toLayer.add(marker);
            return;
        }
    }
}

function enableMarker(id, active)
{
    if (active)
        adjustMarker(id, layers[0], layers[1], '../map_pin_red.png');
    else
        adjustMarker(id, layers[1], layers[0], '../map_pin_grey.png');
}

function addMarker(id, lat, lng, active)
{
    var marker = new Microsoft.Maps.Pushpin(
        new Microsoft.Maps.Location(lat, lng), {
            anchor   : new Microsoft.Maps.Point(11, 35),
            icon     : '../map_pin_grey.png',
            draggable: true
        });
    marker.metadata = {id: id};
    if (active)
    {
        marker.setOptions({icon: '../map_pin_red.png'});
        layers[1].add(marker);
    }
    else
        layers[0].add(marker);
    Microsoft.Maps.Events.addHandler(marker, 'dragstart', markerClick);
    Microsoft.Maps.Events.addHandler(marker, 'drag', markerDrag);
    Microsoft.Maps.Events.addHandler(marker, 'dragend', markerDragEnd);
}

function markerClick(event)
{
    var marker = event.target;
    python.marker_click(marker.metadata.id);
}

function markerDrag(event)
{
    var marker = event.target;
    var loc = marker.getLocation();
    python.marker_drag(loc.latitude, loc.longitude);
}

function markerDragEnd(event)
{
    var marker = event.target;
    var loc = marker.getLocation();
    python.marker_drag_end(loc.latitude, loc.longitude, marker.metadata.id);
}

function markerDrop(x, y)
{
    var position = map.tryPixelToLocation(
        new Microsoft.Maps.Point(x, y), Microsoft.Maps.PixelReference.page);
    python.marker_drop(position.latitude, position.longitude);
}

function delMarker(id)
{
    for (var j = 0; j < layers.length; j++)
    {
        var markers = layers[j].getPrimitives();
        for (var i = 0; i < markers.length; i++)
            if (markers[i].metadata.id == id)
            {
                layers[j].remove(marker);
                return markers[i];
            }
    }
}
