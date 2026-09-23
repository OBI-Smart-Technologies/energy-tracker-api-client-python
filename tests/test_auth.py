from __future__ import annotations

from obi_energy_tracker import static_token_provider


class TestStaticTokenProvider:
    async def test_returns_the_token(self) -> None:
        assert await static_token_provider("abc")() == "abc"

    async def test_returns_the_same_token_on_every_call(self) -> None:
        provider = static_token_provider("abc")

        assert [await provider(), await provider()] == ["abc", "abc"]
