import asyncio

from myUtils.douyin_benchmark import dismiss_douyin_login_popup


class FakeLocator:
    def __init__(self, count=0, visible=False, wait_fails=False):
        self._count = count
        self._visible = visible
        self._wait_fails = wait_fails
        self.clicked = False
        self.first = self

    async def count(self):
        return self._count

    async def is_visible(self):
        return self._visible

    async def click(self, force=False):
        self.clicked = force

    async def wait_for(self, **_kwargs):
        if self._wait_fails:
            raise TimeoutError


class FakeKeyboard:
    def __init__(self):
        self.pressed = []

    async def press(self, key):
        self.pressed.append(key)


class FakePage:
    def __init__(self, panel, close_button):
        self.panel = panel
        self.close_button = close_button
        self.keyboard = FakeKeyboard()
        self.evaluated = []

    def locator(self, selector):
        if selector.startswith("#login-panel-new, "):
            return self.panel
        return self.close_button

    async def evaluate(self, script):
        self.evaluated.append(script)


def test_dismiss_login_popup_clicks_close_button():
    panel = FakeLocator(count=1, visible=True)
    close_button = FakeLocator(count=1, visible=True)
    page = FakePage(panel, close_button)

    dismissed = asyncio.run(dismiss_douyin_login_popup(page))

    assert dismissed is True
    assert close_button.clicked is True
    assert page.keyboard.pressed == []


def test_dismiss_login_popup_is_noop_when_absent():
    page = FakePage(FakeLocator(), FakeLocator())

    dismissed = asyncio.run(dismiss_douyin_login_popup(page))

    assert dismissed is False
