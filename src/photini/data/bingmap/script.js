//  Photini - a simple photo metadata editor.
//  http://github.com/jim-easterbrook/Photini
//  Copyright (C) 2012-17  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

var defaultPushpinIcon;
var map;
var markers = {};
var searchManager;

function initialize()
{
    var mapOptions = {
        credentials: initData.api_key,
        center: new Microsoft.Maps.Location(initData.lat, initData.lng),
        zoom: initData.zoom,
        mapTypeId: Microsoft.Maps.MapTypeId.road,
        disableBirdseye: true,
        enableClickableLogo: false,
        enableSearchLogo: false,
        showLocateMeButton: false,
        showTermsLink: false,
        navigationBarMode: Microsoft.Maps.NavigationBarMode.compact,
        navigationBarOrientation: Microsoft.Maps.NavigationBarOrientation.vertical,
        };
    map = new Microsoft.Maps.Map("#mapDiv", mapOptions);
    Microsoft.Maps.Events.addHandler(map, 'viewchangeend', newBounds);
    Microsoft.Maps.loadModule(
        'Microsoft.Maps.Search', {callback: searchModuleLoaded});
    python.initialize_finished();
}

function searchModuleLoaded()
{
    searchManager = new Microsoft.Maps.Search.SearchManager(map);
}

function newBounds()
{
    var centre = map.getCenter();
    python.new_bounds(centre.latitude, centre.longitude, map.getZoom());
}

function setView(lat, lng, zoom)
{
    map.setView({center: new Microsoft.Maps.Location(lat, lng), zoom: zoom});
}

function getMapBounds()
{
    var map_bounds = map.getBounds();
    return [map_bounds.getWest(), map_bounds.getNorth(),
            map_bounds.getEast(), map_bounds.getSouth()];
}

function adjustBounds(lat0, lng0, lat1, lng1)
{
    var bounds = Microsoft.Maps.LocationRect.fromCorners(
        new Microsoft.Maps.Location(lat0, lng0), new Microsoft.Maps.Location(lat1, lng1));
    map.setView({bounds: bounds});
}

function fitPoints(points)
{
    var locations = [];
    for (var i = 0; i < points.length; i++)
    {
        locations.push(new Microsoft.Maps.Location(points[i][0], points[i][1]));
    }
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
        map.setView({bounds: bounds});
    else if (mapBounds.intersects(bounds))
        map.setView({bounds: bounds, zoom: map.getZoom()});
    else
        map.setView({center: bounds.center, zoom: map.getZoom()});
}

function enableMarker(id, active)
{
    var marker = markers[id];
    if (!marker)
        return;
    if (active)
        marker.setOptions({
            color: 'Orchid',
            zIndex: 1
            });
    else
        marker.setOptions({
            color: 'DimGrey',
            zIndex: 0
            });
}

function addMarker(id, lat, lng, active)
{
    var position = new Microsoft.Maps.Location(lat, lng);
    if (markers[id])
    {
        markers[id].setLocation(position);
        return;
    }
    var marker = new Microsoft.Maps.Pushpin(position, {draggable: true});
    defaultPushpinIcon = marker.getIcon();
    map.entities.push(marker);
    markers[id] = marker;
    marker._id = id;
    Microsoft.Maps.Events.addHandler(marker, 'click', markerClick);
    Microsoft.Maps.Events.addHandler(marker, 'dragstart', markerDragStart);
    Microsoft.Maps.Events.addHandler(marker, 'drag', markerDrag);
    Microsoft.Maps.Events.addHandler(marker, 'dragend', markerDrag);
    enableMarker(id, active);
}

function markerClick(event)
{
    var marker = event.target;
    python.marker_click(marker._id);
}

function markerDragStart(event)
{
    var marker = event.target;
    python.marker_click(marker._id);
}

function markerDrag(event)
{
    var marker = event.target;
    var loc = marker.getLocation();
    python.marker_drag(loc.latitude, loc.longitude, marker._id);
}

function delMarker(id)
{
    if (markers[id])
    {
        map.entities.remove(markers[id]);
        delete markers[id];
    }
}

function removeMarkers()
{
    map.entities.clear();
    markers = {};
}

function latLngFromPixel(x, y)
{
    var position = map.tryPixelToLocation(
        new Microsoft.Maps.Point(x, y), Microsoft.Maps.PixelReference.page);
    return [position.latitude, position.longitude];
}

function search(search_string)
{
    var geocodeRequest = {
        where: search_string,
        count: 20,
        callback: geocodeCallback,
        errorCallback: errCallback
        };
    searchManager.geocode(geocodeRequest);
}

function geocodeCallback(geocodeResult, userData)
{
    for (var i = 0; i < geocodeResult.results.length; i++)
    {
        var view = geocodeResult.results[i].bestView;
        python.search_result(
            view.getNorth(), view.getEast(), view.getSouth(), view.getWest(),
        geocodeResult.results[i].name);
    }
}

function errCallback(geocodeRequest)
{
    alert("Search fail.");
}
