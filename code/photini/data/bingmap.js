//  Photini - a simple photo metadata editor.
//  http://github.com/jim-easterbrook/Photini
//  Copyright (C) 2012  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

function initialize(lat, lng, zoom)
{
  var mapOptions = {
    credentials: api_key,
    center: new Microsoft.Maps.Location(lat, lng),
    zoom: zoom,
    mapTypeId: Microsoft.Maps.MapTypeId.road,
    enableSearchLogo: false,
  };
  map = new Microsoft.Maps.Map(document.getElementById("mapDiv"), mapOptions);
  Microsoft.Maps.Events.addHandler(map, 'viewchangeend', newBounds);
  Microsoft.Maps.loadModule(
    'Microsoft.Maps.Search', {callback: searchModuleLoaded});
}

function searchModuleLoaded()
{
  searchManager = new Microsoft.Maps.Search.SearchManager(map);
}

function newBounds()
{
  var centre = map.getCenter();
  var zoom = map.getZoom();
  python.new_bounds(centre.latitude, centre.longitude, zoom);
}

function setView(lat, lng, zoom)
{
  map.setView({center: new Microsoft.Maps.Location(lat, lng), zoom: zoom});
}

function seeAllMarkers()
{
  var locations = [];
  for (var path in markers)
    locations.push(markers[path].getLocation());
  if (locations.length == 0)
    return;
  var bounds = Microsoft.Maps.LocationRect.fromLocations(locations);
  var zoom = map.getZoom();
  map.setView({bounds: bounds});
  if (map.getZoom() > zoom)
    map.setView({zoom: zoom});
}

function goTo(lat, lng)
{
  map.setView({
    center: new Microsoft.Maps.Location(lat, lng),
    zoom: Math.min(Math.max(map.getZoom(), 11), 16)
  });
}

function enableMarker(path, active)
{
  var marker = markers[path];
  if (active)
    marker.setOptions({
      draggable: true,
      text: 'X',
      zIndex: 1
    });
  else
    marker.setOptions({
      draggable: false,
      text: '',
      zIndex: 0
    });
}

function addMarker(path, lat, lng, label, active)
{
  var position = new Microsoft.Maps.Location(lat, lng);
  if (markers[path])
  {
    markers[path].setLocation(position);
    return;
  }
  var marker = new Microsoft.Maps.Pushpin(position, {});
  map.entities.push(marker);
  markers[path] = marker;
  marker._path = path;
  Microsoft.Maps.Events.addHandler(marker, 'dragstart', markerDragStart);
  Microsoft.Maps.Events.addHandler(marker, 'drag', markerDragEnd);
  Microsoft.Maps.Events.addHandler(marker, 'dragend', markerDragEnd);
  enableMarker(path, active)
}

function markerDragStart(event)
{
  var marker = event.entity;
  python.marker_drag_start(marker._path);
}

function markerDragEnd(event)
{
  var marker = event.entity;
  var loc = marker.getLocation();
  python.marker_drag_end(loc.latitude, loc.longitude, marker._path);
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
    var loc = geocodeResult.results[i].location;
    python.search_result(
      loc.latitude, loc.longitude, geocodeResult.results[i].name);
  }
}

function errCallback(geocodeRequest)
{
   alert("Search fail.");
}
