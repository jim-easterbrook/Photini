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

var map;
var markers = {};
var searchManager;

function loadMap()
{
    var mapOptions = {
        credentials: api_key,
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
}

function searchModuleLoaded()
{
    searchManager = new Microsoft.Maps.Search.SearchManager(map);
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
        marker.setOptions({color: 'Orchid', zIndex: 1});
    else
        marker.setOptions({color: 'DimGrey', zIndex: 0});
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
    map.entities.push(marker);
    markers[id] = marker;
    marker._id = id;
    Microsoft.Maps.Events.addHandler(marker, 'click', markerClick);
    Microsoft.Maps.Events.addHandler(marker, 'dragstart', markerClick);
    Microsoft.Maps.Events.addHandler(marker, 'drag', markerDrag);
    Microsoft.Maps.Events.addHandler(marker, 'dragend', markerDrag);
    enableMarker(id, active);
}

function markerClick(event)
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

function markerDrop(x, y)
{
    var position = map.tryPixelToLocation(
        new Microsoft.Maps.Point(x, y), Microsoft.Maps.PixelReference.page);
    python.marker_drop(position.latitude, position.longitude);
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
    python.log(40, "geocode request fail: " + JSON.stringify(geocodeRequest));
}

function reverseGeocode(lat, lng)
{
    searchManager.reverseGeocode({
        location: new Microsoft.Maps.Location(lat, lng),
        includeCountryIso2: true,
        callback: reverseGeocodeCallback,
        errorCallback: errCallback
        });
}

function reverseGeocodeCallback(geocodeResult, userData)
{
    var country_code = geocodeResult.address.countryRegionISO2;
    var country_name = geocodeResult.address.countryRegion;
    var province_state = geocodeResult.address.adminDistrict;
    if (geocodeResult.address.district)
        province_state = geocodeResult.address.district + ", " + province_state;
    var city = geocodeResult.address.locality;
    var sublocation = geocodeResult.address.addressLine;
    python.set_location_taken(
        "", country_code, country_name, province_state, city, sublocation);
}
