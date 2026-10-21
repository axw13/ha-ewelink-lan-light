"""Exercise actual bulb methods with a fake transport; no HA/device connections."""
import ast
from pathlib import Path
import typing
import unittest

source = ast.parse((Path(__file__).resolve().parents[1] / 'custom_components/ewelink_lan_light/light.py').read_text())
parts = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in
         {'ha_to_br', 'br_to_ha', 'kelvin_to_ct', 'ct_to_kelvin'}]
entity = next(n for n in source.body if isinstance(n, ast.ClassDef))
entity.body = [n for n in entity.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name in {'_dimmable_payload', 'async_prepare_color', 'async_turn_on'}]
parts.append(entity)

class Base:
    def async_write_ha_state(self):
        pass

class Mode:
    RGB = 'rgb'
    COLOR_TEMP = 'color_temp'

namespace = {'Any': typing.Any, 'LightEntity': Base, 'ColorMode': Mode,
             'HomeAssistantError': RuntimeError,
             'ATTR_BRIGHTNESS': 'brightness', 'ATTR_RGB_COLOR': 'rgb_color',
             'ATTR_COLOR_TEMP_KELVIN': 'color_temp_kelvin',
             'MIN_KELVIN': 2000, 'MAX_KELVIN': 6500}
exec(compile(ast.fix_missing_locations(ast.Module(body=parts, type_ignores=[])),
             'actual_light_methods', 'exec'), namespace)

class Device:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    async def async_send(self, command, payload):
        self.calls.append((command, payload))
        if self.fail:
            raise RuntimeError('test transport failure')

def bulb(fail=False):
    cls = namespace['EweLinkLanLight']
    b = cls.__new__(cls)
    b._device = Device(fail)
    b._attr_is_on = False
    b._attr_brightness = 255
    b._attr_color_mode = Mode.COLOR_TEMP
    b._attr_color_temp_kelvin = 4000
    b._attr_rgb_color = (255, 255, 255)
    return b

class ColourFirstTests(unittest.IsolatedAsyncioTestCase):
    async def test_preparation_never_issues_power_or_claims_on_state(self):
        b = bulb()
        await b.async_prepare_color(rgb_color=[0, 56, 0], brightness_pct=2)
        self.assertFalse(b._attr_is_on)
        self.assertEqual(b._device.calls, [('dimmable', {
            'ltype': 'color', 'color': {'br': 2, 'r': 0, 'g': 56, 'b': 0}})])

    async def test_prepare_then_power_preserves_command_order(self):
        b = bulb()
        await b.async_prepare_color(rgb_color=[0, 56, 0], brightness_pct=2)
        await b.async_turn_on()
        self.assertEqual([x[0] for x in b._device.calls], ['dimmable', 'switch'])
        self.assertEqual(b._device.calls[-1][1], {'switch': 'on'})

    async def test_failed_preparation_does_not_commit_state(self):
        b = bulb(True)
        with self.assertRaises(RuntimeError):
            await b.async_prepare_color(rgb_color=[0, 56, 0], brightness_pct=2)
        self.assertFalse(b._attr_is_on)
        self.assertEqual(b._attr_brightness, 255)
        self.assertEqual(b._attr_color_mode, Mode.COLOR_TEMP)

    async def test_default_combined_turn_on_keeps_existing_order(self):
        b = bulb()
        await b.async_turn_on(rgb_color=[0, 56, 0], brightness=5)
        self.assertEqual([x[0] for x in b._device.calls], ['switch', 'dimmable'])

    async def test_white_preparation_then_power_has_expected_temperature(self):
        b = bulb()
        await b.async_prepare_color(color_temp_kelvin=6500, brightness_pct=100)
        self.assertFalse(b._attr_is_on)
        self.assertEqual(b._device.calls, [('dimmable', {
            'ltype': 'white', 'white': {'br': 100, 'ct': 100}})])
        self.assertEqual(b._attr_color_temp_kelvin, 6500)
        self.assertEqual(b._attr_color_mode, Mode.COLOR_TEMP)
        await b.async_turn_on()
        self.assertEqual([x[0] for x in b._device.calls], ['dimmable', 'switch'])

    async def test_missing_or_conflicting_colour_fails_before_any_command(self):
        for kwargs in [{}, {'rgb_color': [0, 56, 0], 'color_temp_kelvin': 6500}]:
            b = bulb()
            with self.assertRaises(RuntimeError):
                await b.async_prepare_color(brightness_pct=100, **kwargs)
            self.assertEqual(b._device.calls, [])

    async def test_failed_white_preparation_preserves_cached_temperature(self):
        b = bulb(True)
        with self.assertRaises(RuntimeError):
            await b.async_prepare_color(color_temp_kelvin=6500, brightness_pct=100)
        self.assertEqual(b._attr_color_temp_kelvin, 4000)
        self.assertFalse(b._attr_is_on)

if __name__ == '__main__':
    unittest.main()
