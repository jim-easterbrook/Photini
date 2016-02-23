//  Photini - a simple photo metadata editor.
//  http://github.com/jim-easterbrook/Photini
//  Copyright (C) 2012-16  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

var geocoder;
var map;
var markers = {};

function initialize(lat, lng, zoom)
{
  var mapOptions =
  {
    center: new google.maps.LatLng(lat, lng),
    panControl: true,
    streetViewControl: false,
    zoom: zoom,
    mapTypeId: google.maps.MapTypeId.ROADMAP
  };
  map = new google.maps.Map(document.getElementById("mapDiv"), mapOptions);
  geocoder = new google.maps.Geocoder();
  google.maps.event.addListener(map, 'idle', newBounds);
}

function newBounds()
{
  var centre = map.getCenter();
  python.new_bounds(centre.lat(), centre.lng(), map.getZoom());
}

function setView(lat, lng, zoom)
{
  map.setZoom(zoom)
  map.panTo(new google.maps.LatLng(lat, lng));
}

function seeMarkers(ids)
{
  var bounds;
  for (var i = 0; i < ids.length; i++)
  {
    var marker = markers[ids[i]];
    if (marker)
    {
      var position = marker.getPosition();
      if (bounds)
        bounds.extend(position);
      else
        bounds = new google.maps.LatLngBounds(position, position);
    }
  }
  if (!bounds)
    return;
  var map_span = map.getBounds().toSpan();
  var map_height = map_span.lat();
  var map_width = map_span.lng();
  var ne = bounds.getNorthEast();
  var sw = bounds.getSouthWest();
  bounds.extend((new google.maps.LatLng(ne.lat() + (map_height / 20.0),
					ne.lng() + (map_width / 20.0))));
  bounds.extend((new google.maps.LatLng(sw.lat() - (map_height / 20.0),
					sw.lng() - (map_width / 20.0))));
  var span = bounds.toSpan();
  if ((span.lat() > map_height) | (span.lng() > map_width))
    map.fitBounds(bounds);
  else
    map.panToBounds(bounds);
}

function goTo(lat, lng)
{
  var zoom = map.getZoom();
  if (zoom < 11)
    map.setZoom(11);
  if (zoom > 16)
    map.setZoom(16)
  map.panTo(new google.maps.LatLng(lat, lng));
}

function enableMarker(id, active)
{
  var marker = markers[id];
  if (marker)
  {
    if (active)
      marker.setOptions({
        icon: '',
        zIndex: 1
      });
    else
      marker.setOptions({
        icon: 'grey_marker.png',
        zIndex: 0
      });
  }
}

function addMarker(id, lat, lng, active)
{
  var position = new google.maps.LatLng(lat, lng);
  if (markers[id])
  {
    markers[id].setPosition(position);
    return;
  }
  var marker = new google.maps.Marker(
    {
      position: position,
      map: map,
      draggable: true,
    });
  markers[id] = marker;
  marker._id = id;
  google.maps.event.addListener(marker, 'click', function(event)
  {
    python.marker_click(this._id)
  });
  google.maps.event.addListener(marker, 'dragstart', function(event)
  {
    python.marker_click(this._id)
  });
  google.maps.event.addListener(marker, 'drag', function(event)
  {
    var loc = event.latLng;
    python.marker_drag(loc.lat(), loc.lng(), this._id);
  });
  google.maps.event.addListener(marker, 'dragend', function(event)
  {
    var loc = event.latLng;
    python.marker_drag_end(loc.lat(), loc.lng(), this._id);
  });
  enableMarker(id, active)
}

function delMarker(id)
{
  if (markers[id])
  {
    google.maps.event.clearInstanceListeners(markers[id]);
    markers[id].setMap(null);
    delete markers[id];
  }
}

function removeMarkers()
{
  for (var id in markers)
  {
    google.maps.event.clearInstanceListeners(markers[id]);
    markers[id].setMap(null);
  }
  markers = {};
}

function latLngFromPixel(x, y)
{
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
  return [position.lat(), position.lng()];
}

function search(search_string)
{
  geocoder.geocode(
    {
      'address': search_string,
      bounds: map.getBounds(),
    },
    function(results, status)
    {
      if (status == google.maps.GeocoderStatus.OK)
	{
	  for (i in results)
	  {
	    loc = results[i].geometry.location;
	    python.search_result(
	      loc.lat(), loc.lng(), results[i].formatted_address);
	  }
	}
	else
	  alert("Search fail, code:" + status);
    }
  );
}
