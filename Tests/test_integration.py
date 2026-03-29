"""End-to-end integration test: MCP AbletonConnection <-> Remote Script TcpServer.

Proves the full round-trip works: MCP client sends a CommandRequest over TCP,
the Remote Script TcpServer receives it, dispatches via the Dispatcher, and
the response comes back as a valid CommandResponse.  The _Framework stub and
remote_script sys.path setup live in conftest.py.
"""

from __future__ import annotations

import threading

import pytest
from AbletonLiveMCP.dispatcher import Dispatcher
from AbletonLiveMCP.tcp_server import TcpServer

from mcp_ableton.connection import AbletonConnection
from mcp_ableton.protocol import CommandRequest


class _FakeControlSurface:
    pass


class _EchoHandler:
    def handle_get_info(self, params):
        return {"tempo": 120.0, "is_playing": False}

    def handle_start_recording(self, params):
        return {
            "action": "start_recording",
            "is_recording": True,
            "is_playing": True,
        }


class _BrowserHandler:
    def handle_get_tree(self, params):
        return {
            "categories": [
                {
                    "name": "Instruments",
                    "uri": "browser:instruments",
                    "is_folder": True,
                    "is_loadable": False,
                    "children": [
                        {
                            "name": "Synths",
                            "uri": "browser:instruments/synths",
                            "is_folder": True,
                            "is_loadable": False,
                            "children": [
                                {
                                    "name": "Analog",
                                    "uri": "browser:instruments/synths/analog",
                                    "is_folder": False,
                                    "is_loadable": True,
                                    "children": [],
                                }
                            ],
                        }
                    ],
                }
            ]
        }


class _DeviceHandler:
    def handle_get_parameters(self, params):
        return {
            "track_index": 1,
            "device_index": 2,
            "device_name": "Analog",
            "parameters": [
                {
                    "parameter_index": 1,
                    "name": "Device On",
                    "value": 1.0,
                    "min": 0.0,
                    "max": 1.0,
                    "is_quantized": True,
                },
                {
                    "parameter_index": 2,
                    "name": "Filter Freq",
                    "value": 5000.0,
                    "min": 20.0,
                    "max": 20000.0,
                    "is_quantized": False,
                },
            ],
        }


class _MixerHandler:
    def handle_get_master_info(self, params):
        return {
            "name": "Master",
            "volume": 0.88,
            "pan": 0.0,
        }

    def handle_get_return_tracks(self, params):
        return {
            "return_tracks": [
                {
                    "return_index": 1,
                    "name": "A Return",
                    "volume": 0.61,
                    "pan": -0.15,
                }
            ]
        }

    def handle_set_send_level(self, params):
        return {
            "track_index": params["track_index"],
            "send_index": params["send_index"],
            "level": params["level"],
        }


class _ArrangementHandler:
    def handle_get_clips(self, params):
        return {
            "track_index": None,
            "clips": [
                {
                    "track_index": 1,
                    "clip_index": 1,
                    "name": "Verse",
                    "start_time": 0.0,
                    "end_time": 8.0,
                    "length": 8.0,
                    "is_audio_clip": False,
                    "is_midi_clip": True,
                }
            ],
        }


class _SceneHandler:
    def handle_get_all(self, params):
        return {
            "scenes": [
                {
                    "scene_index": 1,
                    "name": "Intro",
                    "is_empty": False,
                    "is_triggered": False,
                    "tempo_enabled": True,
                    "tempo": 120.0,
                    "time_signature_enabled": True,
                    "time_signature_numerator": 4,
                    "time_signature_denominator": 4,
                },
                {
                    "scene_index": 2,
                    "name": "Breakdown",
                    "is_empty": True,
                    "is_triggered": True,
                    "tempo_enabled": False,
                    "tempo": None,
                    "time_signature_enabled": False,
                    "time_signature_numerator": None,
                    "time_signature_denominator": None,
                },
            ]
        }


@pytest.fixture
def tcp_server():
    """Start a real TcpServer in a background thread on an OS-assigned port."""
    cs = _FakeControlSurface()
    dispatcher = Dispatcher(cs)
    dispatcher.register("session", _EchoHandler())
    dispatcher.register("browser", _BrowserHandler())
    dispatcher.register("device", _DeviceHandler())
    dispatcher.register("mixer", _MixerHandler())
    dispatcher.register("arrangement", _ArrangementHandler())
    dispatcher.register("scene", _SceneHandler())

    logs: list[str] = []
    server = TcpServer(
        dispatcher=dispatcher,
        log_fn=lambda msg: logs.append(msg),
        host="127.0.0.1",
        port=0,
    )

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server.wait_until_ready()

    yield server.port, server, logs

    server.shutdown()
    thread.join(timeout=3)


class TestFullRoundTrip:
    async def test_ping_via_tcp(self, tcp_server) -> None:
        port, server, logs = tcp_server
        conn = AbletonConnection(host="127.0.0.1", port=port, max_retries=1)
        await conn.connect()

        assert await conn.ping() is True

        await conn.disconnect()

    async def test_command_via_tcp(self, tcp_server) -> None:
        port, server, logs = tcp_server
        conn = AbletonConnection(host="127.0.0.1", port=port, max_retries=1)
        await conn.connect()

        req = CommandRequest(command="session.get_info", id="e2e-1")
        resp = await conn.send_command(req)

        assert resp.status == "ok"
        assert resp.id == "e2e-1"
        assert resp.result == {"tempo": 120.0, "is_playing": False}

        await conn.disconnect()

    async def test_unknown_command_via_tcp(self, tcp_server) -> None:
        port, server, logs = tcp_server
        conn = AbletonConnection(host="127.0.0.1", port=port, max_retries=1)
        await conn.connect()

        req = CommandRequest(command="bogus.action", id="e2e-2")
        resp = await conn.send_command(req)

        assert resp.status == "error"
        assert resp.error is not None
        assert resp.error.code == "UNKNOWN_COMMAND"

        await conn.disconnect()

    async def test_recording_payload_via_tcp(self, tcp_server) -> None:
        port, server, logs = tcp_server
        conn = AbletonConnection(host="127.0.0.1", port=port, max_retries=1)
        await conn.connect()

        req = CommandRequest(command="session.start_recording", id="recording-1")
        resp = await conn.send_command(req)

        assert resp.status == "ok"
        assert resp.id == "recording-1"
        assert resp.result == {
            "action": "start_recording",
            "is_recording": True,
            "is_playing": True,
        }

        await conn.disconnect()

    async def test_multiple_commands_via_tcp(self, tcp_server) -> None:
        port, server, logs = tcp_server
        conn = AbletonConnection(host="127.0.0.1", port=port, max_retries=1)
        await conn.connect()

        for i in range(5):
            req = CommandRequest(command="system.ping", id=f"multi-{i}")
            resp = await conn.send_command(req)
            assert resp.status == "ok"
            assert resp.id == f"multi-{i}"

        await conn.disconnect()

    async def test_nested_browser_payload_via_tcp(self, tcp_server) -> None:
        port, server, logs = tcp_server
        conn = AbletonConnection(host="127.0.0.1", port=port, max_retries=1)
        await conn.connect()

        req = CommandRequest(command="browser.get_tree", id="browser-1")
        resp = await conn.send_command(req)

        assert resp.status == "ok"
        assert resp.id == "browser-1"
        assert resp.result is not None
        category = resp.result["categories"][0]
        assert category["name"] == "Instruments"
        assert category["children"][0]["children"][0]["name"] == "Analog"

        await conn.disconnect()

    async def test_device_payload_via_tcp(self, tcp_server) -> None:
        port, server, logs = tcp_server
        conn = AbletonConnection(host="127.0.0.1", port=port, max_retries=1)
        await conn.connect()

        req = CommandRequest(command="device.get_parameters", id="device-1")
        resp = await conn.send_command(req)

        assert resp.status == "ok"
        assert resp.id == "device-1"
        assert resp.result is not None
        assert resp.result["device_name"] == "Analog"
        assert resp.result["parameters"][0]["parameter_index"] == 1
        assert resp.result["parameters"][1]["name"] == "Filter Freq"

        await conn.disconnect()

    async def test_scene_payload_via_tcp(self, tcp_server) -> None:
        port, server, logs = tcp_server
        conn = AbletonConnection(host="127.0.0.1", port=port, max_retries=1)
        await conn.connect()

        req = CommandRequest(command="scene.get_all", id="scene-1")
        resp = await conn.send_command(req)

        assert resp.status == "ok"
        assert resp.id == "scene-1"
        assert resp.result is not None
        assert resp.result["scenes"][0]["name"] == "Intro"
        assert resp.result["scenes"][1]["tempo"] is None
        assert resp.result["scenes"][1]["time_signature_denominator"] is None

        await conn.disconnect()

    async def test_mixer_payload_via_tcp(self, tcp_server) -> None:
        port, server, logs = tcp_server
        conn = AbletonConnection(host="127.0.0.1", port=port, max_retries=1)
        await conn.connect()

        req = CommandRequest(command="mixer.get_master_info", id="mixer-1")
        resp = await conn.send_command(req)

        assert resp.status == "ok"
        assert resp.id == "mixer-1"
        assert resp.result is not None
        assert resp.result == {
            "name": "Master",
            "volume": 0.88,
            "pan": 0.0,
        }

        await conn.disconnect()

    async def test_return_tracks_payload_via_tcp(self, tcp_server) -> None:
        port, server, logs = tcp_server
        conn = AbletonConnection(host="127.0.0.1", port=port, max_retries=1)
        await conn.connect()

        req = CommandRequest(command="mixer.get_return_tracks", id="mixer-returns-1")
        resp = await conn.send_command(req)

        assert resp.status == "ok"
        assert resp.id == "mixer-returns-1"
        assert resp.result is not None
        assert resp.result == {
            "return_tracks": [
                {
                    "return_index": 1,
                    "name": "A Return",
                    "volume": 0.61,
                    "pan": -0.15,
                }
            ]
        }

        await conn.disconnect()

    async def test_set_send_level_payload_via_tcp(self, tcp_server) -> None:
        port, server, logs = tcp_server
        conn = AbletonConnection(host="127.0.0.1", port=port, max_retries=1)
        await conn.connect()

        req = CommandRequest(
            command="mixer.set_send_level",
            params={"track_index": 2, "send_index": 1, "level": 0.37},
            id="mixer-send-1",
        )
        resp = await conn.send_command(req)

        assert resp.status == "ok"
        assert resp.id == "mixer-send-1"
        assert resp.result == {
            "track_index": 2,
            "send_index": 1,
            "level": 0.37,
        }

        await conn.disconnect()

    async def test_arrangement_payload_via_tcp(self, tcp_server) -> None:
        port, server, logs = tcp_server
        conn = AbletonConnection(host="127.0.0.1", port=port, max_retries=1)
        await conn.connect()

        req = CommandRequest(command="arrangement.get_clips", id="arrangement-1")
        resp = await conn.send_command(req)

        assert resp.status == "ok"
        assert resp.id == "arrangement-1"
        assert resp.result is not None
        assert resp.result["track_index"] is None
        assert resp.result["clips"][0]["name"] == "Verse"
        assert resp.result["clips"][0]["is_midi_clip"] is True

        await conn.disconnect()
