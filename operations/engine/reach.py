"""Reported lateral reach with assumed standing bands; simulation helpers only."""
from __future__ import annotations
import math


def apply_reach_policy(config, layout, policy):
    """Give individual trays resources and serving-side standing bands in meters."""
    config['reach_policy'] = policy
    config['selection_policy'] = 'available_ingredient_first'
    config['local_basket'] = True
    fixtures = {f['entity_id']: f for f in layout['fixtures']}
    resources = {r['resource_id']: r for r in config['resources']}
    layout['reach_zones'] = {}
    for tray in policy['tray_resources']:
        fixture = fixtures[tray['entity_id']]
        location = tray['location']
        # Counter long edge runs along Y; worker stands on +X (interior) side.
        center_y = fixture['y'] + fixture['height']/2
        access_x = fixture['x'] + fixture['width'] + .32
        if tray['counter']:
            layout['locations'][location] = {'x': access_x, 'y': center_y,
                                            'label': fixture['label'] + ' · alcance ±50 cm'}
            half_width = policy['lateral_half_width_m']
            half_depth = policy['standing_depth_m']/2
            layout['reach_zones'][location] = {
                'min_x': access_x-half_depth, 'max_x': access_x+half_depth,
                'min_y': center_y-half_width, 'max_y': center_y+half_width,
                'tray_center_m': [fixture['x']+fixture['width']/2, center_y],
                'resource_id': tray['resource_id'], 'label': fixture['label'],
                'evidence': policy['evidence'],
            }
        else:
            # Retain existing provisional standing side for potato/chicharron.
            loc = layout['locations'][location]
            layout['reach_zones'][location] = {
                'min_x': loc['x']-.22, 'max_x': loc['x']+.22,
                'min_y': loc['y']-.5, 'max_y': loc['y']+.5,
                'tray_center_m': [fixture['x']+fixture['width']/2, center_y],
                'resource_id': tray['resource_id'], 'label': fixture['label'],
                'evidence': 'assumed_standing_side_with_reported_lateral_reach',
            }
        if tray['counter']:
            zone=layout['reach_zones'][location]
            room=next(f for f in layout['fixtures'] if f['class']=='room')
            obstacles=[f for f in layout['fixtures'] if f['class'] not in {'room','door'}]
            def clear(x,y):
                return (room['x']<x<room['x']+room['width'] and room['y']<y<room['y']+room['height']
                        and not any(f['x']-.1<x<f['x']+f['width']+.1 and f['y']-.1<y<f['y']+f['height']+.1 for f in obstacles))
            candidates=[(zone['min_x']+i*.02,zone['min_y']+j*.02)
                        for i in range(23) for j in range(51)
                        if clear(zone['min_x']+i*.02,zone['min_y']+j*.02)]
            if not candidates:
                raise ValueError('No standing point inside reach zone: '+location)
            x,y=min(candidates,key=lambda xy:math.dist(xy,(access_x,center_y)))
            layout['locations'][location].update(x=x,y=y)
        layout['resource_locations'][tray['resource_id']] = location
        if location not in layout['worker_access_locations']:
            layout['worker_access_locations'].append(location)
        resources[tray['resource_id']] = {
            'resource_id': tray['resource_id'], 'resource_type': 'tray_access',
            'capacity': policy['default_tray_capacity'],
        }
    resources['resource:counter_front'] = {
        'resource_id': 'resource:counter_front', 'resource_type': 'counter_access',
        'capacity': policy['counter_capacity'],
    }
    config['resources'] = list(resources.values())
    layout['notes'].append(f"Alcance lateral reportado ±50 cm; prueba con {policy['counter_capacity']} personas simultáneas en el frente y 2 por bandeja. Posiciones y capacidades adicionales por validar. Canasto con el trabajador; sin regreso al centro por ingrediente.")
