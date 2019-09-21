//  Photini - a simple photo metadata editor.
//  http://github.com/jim-easterbrook/Photini
//  Copyright (C) 2012-18  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

function loadMap(lat, lng, zoom)
{
    map = L.map(document.getElementById("mapDiv"), {
        center: [lat, lng],
        zoom: zoom,
        });
    L.tileLayer(
        'https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png',
        {
            attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/copyright">' +
                'OpenStreetMap</a> contributors | ' + 
                'Imagery &copy; <a href="https://carto.com/attribution">CARTO</a>',
            maxZoom: 20,
        }).addTo(map);
    commonLoad();
}
