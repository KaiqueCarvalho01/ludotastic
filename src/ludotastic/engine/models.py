"""Model adapters Ludotastic adds on top of Pydantic AI."""

__all__: tuple[str, ...] = (
    "IMAGES_HEADER",
    "TypeSafeImageModel",
    "resolve_model",
)

from typing import ClassVar, Final, override

from pydantic import JsonValue
from pydantic_ai.models import Model, infer_model
from pydantic_ai.models.decision import (
    DecisionModelSettings,
    DecisionRequest,
    DecisionResponse,
)
from pydantic_ai.models.typesafe import TypeSafeModel
from typesafe_sdk import Image

IMAGES_HEADER: Final = "TypeSafe-Danger-Zone-Images"
"""The header TypeSafe needs on every request that carries an image."""


class TypeSafeImageModel(TypeSafeModel):
    """TypeSafe's Jev, able to see images.

    Jev takes images since Jev 1.13, as an experimental feature. Pydantic AI's
    `TypeSafeModel` (2.66) still rejects them, so this fills the gap: Pydantic
    AI already puts each image in the state as `<image N>` and hands the images
    over in `request.images`, and this swaps each placeholder for a TypeSafe
    image reference, attaches the images to the SDK client for the request,
    and adds TypeSafe's opt-in header.

    Requests without images go through exactly as `TypeSafeModel` sends them.
    """

    supports_image_input: ClassVar[bool] = True

    @override
    async def decide(
        self, request: DecisionRequest, model_settings: DecisionModelSettings
    ) -> DecisionResponse:
        """Send one request, with its images attached as TypeSafe assets."""
        if not request.images:
            return await super().decide(request, model_settings)
        images = [Image(image.data) for image in request.images]
        references = {f"<image {n}>": str(image) for n, image in enumerate(images, 1)}
        settings: DecisionModelSettings = {
            **model_settings,
            "extra_headers": {
                **(model_settings.get("extra_headers") or {}),
                IMAGES_HEADER: "true",
            },
        }
        request = DecisionRequest(
            state=_replace(request.state, references),
            questions=request.questions,
            messages=request.messages,
        )
        # The SDK uploads attached images wherever their reference appears.
        with self.client.attach_assets(images):
            return await super().decide(request, settings)


def _replace(value: JsonValue, references: dict[str, str]) -> JsonValue:
    """Swap Pydantic AI's `<image N>` placeholders for TypeSafe references.

    Examples:
        >>> _replace({"text": "Board: <image 1>"}, {"<image 1>": "ref-1"})
        {'text': 'Board: ref-1'}
    """
    if isinstance(value, str):
        for placeholder, reference in references.items():
            value = value.replace(placeholder, reference)
        return value
    if isinstance(value, list):
        return [_replace(item, references) for item in value]
    if isinstance(value, dict):
        return {key: _replace(item, references) for key, item in value.items()}
    return value


def resolve_model(name: str) -> Model:
    """Build a model from its name, using the image-capable class for Jev.

    Examples:
        >>> type(resolve_model("test")).__name__
        'TestModel'
    """
    if name.startswith("typesafe:"):
        return TypeSafeImageModel(name.removeprefix("typesafe:"))
    return infer_model(name)
