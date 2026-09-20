"""Coordinate the two optional Desktop Lonk birds."""

from __future__ import annotations

from pathlib import Path


class Flock:
    """Own the shared Tk root, Lonk/Pip brains, and their pet windows."""

    def __init__(self, root, data, brain_type, pet_type):
        self.root = root
        self.data = Path(data)
        self.brain_type = brain_type
        self.pet_type = pet_type
        self.paused = False
        self.closed = False

        lonk = brain_type(self.data, name="Lonk")
        pip = brain_type(self.data / "Pip", name="Pip")
        self.brains = [lonk, pip]
        self.pets = [
            pet_type(root, lonk, self),
            self._make_peer(root, pip),
        ]
        self.pets[0].peer = self.pets[1] if hasattr(self.pets[0], "peer") else None
        self.pets[1].peer = self.pets[0] if hasattr(self.pets[1], "peer") else None

    def _make_peer(self, root, brain):
        import tkinter as tk
        peer_root = tk.Toplevel(root)
        pet = self.pet_type(peer_root, brain, self)
        left, top, right, bottom = pet.area
        pet.x = max(left, min(pet.x + 150, right - pet.WIDTH))
        pet.tx = pet.x
        pet.position()
        return pet

    def other(self, pet):
        for candidate in self.pets:
            if candidate is not pet:
                return candidate
        raise ValueError("The flock has no other bird")

    def visit(self, pet):
        other = self.other(pet)
        other.follow_peer = pet
        other.follow_until = __import__("time").monotonic() + 12
        return other

    def toggle(self):
        self.paused = not self.paused
        for pet in self.pets:
            pet.paused = self.paused

    def close(self):
        if self.closed:
            return
        self.closed = True
        for pet in self.pets:
            pet.running = False
            if pet.chat_window:
                pet.chat_window.cancel_reply()
        for brain in self.brains:
            brain.save()
        self.root.destroy()
