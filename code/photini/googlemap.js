var geocoder = new google.maps.Geocoder();
var map;
var markers = [];

function initialize()
{
  var mapOptions =
  {
    center: new google.maps.LatLng(%f, %f),
    panControl: true,
    streetViewControl: false,
    scrollwheel: false,
    zoom: %d,
    mapTypeId: google.maps.MapTypeId.ROADMAP
  };
  map = new google.maps.Map(document.getElementById("map_canvas"), mapOptions);
}

function goTo(lat, lng, zoom)
{
  if (map.getZoom() < zoom)
  {
    map.setZoom(zoom);
  }
  map.panTo(new google.maps.LatLng(lat, lng));
}

function addMarker(lat, lng, label)
{
  position = new google.maps.LatLng(lat, lng);
  bounds = new google.maps.LatLngBounds(position, position);
  if (markers)
  {
    for (i in markers)
    {
      bounds.extend(markers[i].getPosition());
    }
  }
  mapSize = map.getBounds().toSpan();
  zoom = map.getZoom();
  boundsSize = bounds.toSpan();
  while (zoom < 16 && mapSize.lat() > boundsSize.lat() * 3 &&
                      mapSize.lng() > boundsSize.lng() * 3)
  {
    zoom = zoom + 1;
    map.setZoom(zoom);
    mapSize = map.getBounds().toSpan();
  }
  while (zoom > 0 && (mapSize.lat() < boundsSize.lat() * 1.2 ||
                      mapSize.lng() < boundsSize.lng() * 1.2))
  {
    zoom = zoom - 1;
    map.setZoom(zoom);
    mapSize = map.getBounds().toSpan();
  }
  map.panTo(bounds.getCenter());
  marker = new google.maps.Marker(
    {
      position: position,
      map: map,
      draggable: true,
      title: label,
    });
  markers.push(marker);
  google.maps.event.addListener(marker, 'dragend', markerDragEnd);
  return true;
}

function removeMarkers()
{
  if (markers)
  {
    for (i in markers)
    {
      markers[i].setMap(null);
    }
    markers.length = 0;
  }
}

function markerDragEnd(event)
{
  loc = event.latLng;
  python.done(loc.lat(), loc.lng(), marker.title);
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
	{
	  python.search_result(0, 0, "");
	}
    }
  );
}
