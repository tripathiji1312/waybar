#!/usr/bin/env python3
import gi
gi.require_version("Playerctl", "2.0")
from gi.repository import Playerctl, GLib
from gi.repository.Playerctl import Player
import argparse
import logging
import sys
import signal
import json
import os
from typing import List, Optional

# Basic logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def signal_handler(sig, frame):
    """Handles termination signals."""
    logger.info("Received signal to stop, exiting.")
    sys.stdout.write("\n")
    sys.stdout.flush()
    sys.exit(0)

class PlayerManager:
    def __init__(self, selected_player: Optional[str] = None, excluded_players: Optional[List[str]] = None):
        self.manager = Playerctl.PlayerManager()
        self.loop = GLib.MainLoop()
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.selected_player = selected_player
        self.excluded_players = excluded_players or []

        # Connect manager signals
        self.manager.connect("name-appeared", self.on_player_appeared)
        self.manager.connect("player-vanished", self.on_player_vanished)

        self.init_players()

    def init_players(self):
        """Initializes all currently running and manageable players."""
        for player_name in self.manager.props.player_names:
            if self._is_player_managed(player_name.name):
                self.add_player(player_name)

    def run(self):
        """Starts the main event loop."""
        logger.info("PlayerManager running. Waiting for events.")
        self.update_display() # Initial display update
        self.loop.run()

    def add_player(self, player_name: Playerctl.PlayerName):
        """Adds and starts managing a new player."""
        logger.info(f"New player appeared: {player_name.name}")
        player = Playerctl.Player.new_from_name(player_name)
        player.connect("playback-status", self.on_event, None)
        player.connect("metadata", self.on_event, None)
        self.manager.manage_player(player)
        self.update_display()

    def _is_player_managed(self, player_name: str) -> bool:
        """Checks if a player should be managed based on selection/exclusion lists."""
        if player_name in self.excluded_players:
            logger.debug(f"Player '{player_name}' is in exclude list. Skipping.")
            return False
        if self.selected_player and self.selected_player != player_name:
            logger.debug(f"Player '{player_name}' is not the selected player. Skipping.")
            return False
        return True

    def on_player_appeared(self, _, player_name: Playerctl.PlayerName):
        """Callback for when a new player is detected."""
        if self._is_player_managed(player_name.name):
            self.add_player(player_name)

    def on_player_vanished(self, _, player: Player):
        """Callback for when a player closes."""
        logger.info(f"Player vanished: {player.props.player_name}")
        self.update_display()

    def on_event(self, player: Player, *args):
        """Generic callback for player events (metadata, playback status)."""
        logger.debug(f"Event from {player.props.player_name}. Re-evaluating display.")
        self.update_display()

    def get_display_player(self) -> Optional[Player]:
        """
        Determines which player should be displayed based on status priority.
        Priority: Playing > Paused.
        Returns the highest priority player or None.
        """
        players = self.manager.props.players
        
        playing_player = None
        paused_player = None

        # Iterate players to find the best candidate
        # We iterate in reverse to prefer the most recently started player
        for player in reversed(players):
            if player.props.playback_status == Playerctl.PlaybackStatus.PLAYING:
                playing_player = player
                break # A playing player has the highest priority
            elif player.props.playback_status == Playerctl.PlaybackStatus.PAUSED:
                if not paused_player: # Only store the first paused player we find
                    paused_player = player
        
        return playing_player or paused_player

    def update_display(self):
        """
        The single source of truth for updating the Waybar output.
        Gets the highest priority player and formats the output for it.
        """
        player = self.get_display_player()

        if not player:
            sys.stdout.write("\n")
            sys.stdout.flush()
            return

        artist = player.get_artist() or ""
        title = player.get_title() or ""

        # Clean up text for display
        artist = artist.replace("&", "&amp;")
        title = title.replace("&", "&amp;")
        
        track_info = ""
        player_name = player.props.player_name

        if "spotify" in player_name.lower() and "mpris:trackid" in player.props.metadata and ":ad:" in player.props.metadata["mpris:trackid"]:
            track_info = "Advertisement"
        elif artist and title:
            track_info = f"{artist} - {title}"
        elif title:
            track_info = title
        elif player_name:
             track_info = player_name
        else:
            track_info = "No track info"


        if player.props.playback_status == Playerctl.PlaybackStatus.PLAYING:
            icon = "󰐊" # Play icon
        else: # Paused or Stopped
            icon = "󰏤" # Pause icon

        output_text = f"{icon} {track_info}"
        
        # Create the JSON output for Waybar
        output = {
            "text": output_text,
            "class": "custom-" + player_name.lower().split('.')[0], # e.g., 'custom-spotify' or 'custom-firefox'
            "alt": f"{player.props.playback_status} on {player_name}",
            "tooltip": f"{artist}\n{title}"
        }

        sys.stdout.write(json.dumps(output) + "\n")
        sys.stdout.flush()


def main():
    # You can still use arguments for manual debugging from a terminal
    parser = argparse.ArgumentParser()
    parser.add_argument("--player", help="Filter for a specific player name")
    parser.add_argument("--exclude", help="Comma-separated list of player names to exclude")
    args = parser.parse_args()

    excluded_list = args.exclude.split(',') if args.exclude else []
    
    manager = PlayerManager(selected_player=args.player, excluded_players=excluded_list)
    manager.run()

if __name__ == "__main__":
    main()