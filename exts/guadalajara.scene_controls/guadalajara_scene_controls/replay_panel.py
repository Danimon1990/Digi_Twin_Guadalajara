"""Kit controls for playback of a local, already computed SimPy run."""
import json
from pathlib import Path
import statistics
import time

import omni.ui as ui

from .replay import Replay


class ReplayPanel:
    def __init__(self, viewport):
        self.viewport = viewport
        self.replay = None
        self.playing = False
        self.updating = False
        self.last = time.monotonic()
        self.window = ui.Window('Guadalajara · SimPy 3D', width=560, height=420, visible=False)
        with self.window.frame:
            with ui.VStack(spacing=6):
                ui.Label('SimPy · reproducción sintética en 3D', height=26)
                self.file = ui.StringField(height=28)
                self.file.model.set_value('')
                with ui.HStack(height=30, spacing=5):
                    ui.Button('Cargar JSON', clicked_fn=self.load)
                    self.play = ui.Button('Play', clicked_fn=self.toggle)
                    ui.Button('Inicio', clicked_fn=lambda: self.seek_fraction(0))
                    ui.Button('Quitar', clicked_fn=self.clear)
                with ui.HStack(height=26):
                    ui.Label('Velocidad ×', width=95)
                    self.speed = ui.FloatField()
                    self.speed.model.set_value(4.0)
                self.slider = ui.FloatSlider(min=0,max=1,height=25)
                self.slider.model.add_value_changed_fn(self.scrub)
                self.status = ui.Label('Pega la ruta local de isaac_replay.json y pulsa Cargar JSON.', height=44, word_wrap=True)
                self.stats = ui.Label('',height=44,word_wrap=True)
                self.rows = ui.Label('',word_wrap=True)

    def show(self):
        self.window.visible = True

    def load(self):
        try:
            viewport = self.viewport()
            if not viewport or not viewport.stage:
                raise ValueError('Abre la escena USD de Guadalajara primero.')
            path = Path(self.file.model.as_string.strip()).expanduser()
            with path.open(encoding='utf-8') as source:
                data = json.load(source)
            self.clear()
            self.replay = Replay(viewport.stage,data)
            stale = (data.get('geometry') or {}).get('matches_current_scene') is False
            self.status.text = 'Corrida sintética · solo lectura.' + (' La geometría usada por la corrida es anterior al archivo Blender.' if stale else '')
            self.seek_fraction(0)
        except Exception as error:
            self.status.text = str(error)

    def toggle(self):
        if not self.replay:
            return
        if self.replay.time >= self.replay.duration:
            self.seek_fraction(0)
        self.playing = not self.playing
        self.last = time.monotonic()
        self.play.text = 'Pause' if self.playing else 'Play'

    def scrub(self, model):
        if not self.updating:
            self.seek_fraction(model.as_float)

    def seek_fraction(self, fraction):
        if self.replay:
            self.render(self.replay.duration*fraction)

    def render(self, seconds):
        replay = self.replay
        data = replay.seek(seconds)
        self.updating = True
        try:
            self.slider.model.set_value(replay.time/replay.duration)
        finally:
            self.updating = False
        done = data['completed']
        mean = f'{statistics.mean(done.values()):.1f} s' if done else '—'
        self.stats.text = (f"{replay.time:.1f} / {replay.duration:.0f} s · {len(replay.actors)} trabajadores"
                           f" · fila: {data['waiting']} · completos: {len(done)}\nAtención media de completados: {mean}")
        names = {'idle':'Libre','ingredient_wait':'Espera ingrediente','product_pick':'Seleccionando',
                 'product_deposit':'En canasto','cutting':'Corte','payment':'Pago','order_taking':'Tomando pedido',
                 'seasoning':'Sazonando','handover':'Entregando','packaging':'Empacando'}
        self.rows.text = '\n'.join(
            f'{label}   {client[0]} · {replay.time-client[1]:.1f} s   {names.get(activity,activity)}' + (f' · {product}' if product else '')
            if client else f'{label}   {names.get(activity,activity)}'
            for label,client,activity,product in data['rows'])

    def update(self):
        if not self.replay:
            return
        try:
            viewport = self.viewport()
            if not viewport or viewport.stage != self.replay.stage:
                self.clear()
                return
            now = time.monotonic()
            if self.playing and now-self.last >= 1/30:
                speed = min(60,max(.25,self.speed.model.as_float))
                self.render(self.replay.time+(now-self.last)*speed)
                self.last = now
                if self.replay.time >= self.replay.duration:
                    self.playing = False
                    self.play.text = 'Play'
        except Exception as error:
            self.clear()
            self.status.text = str(error)

    def clear(self):
        self.playing = False
        self.play.text = 'Play'
        if self.replay:
            self.replay.close()
            self.replay = None
        self.stats.text = self.rows.text = ''

    def destroy(self):
        self.clear()
        self.window.destroy()
