from PIL import Image


def create_png(
    width: int,
    height: int,
    color=(255, 255, 255, 255),
    output_path: str = "image_10x10.png",
):
    """
    Creates and saves a PNG image.

    Args:
        width (int): Image width in pixels.
        height (int): Image height in pixels.
        color (tuple): RGBA color for the background (default white).
        output_path (str): Path to save the PNG.
    """
    # Create a new image with RGBA mode
    img = Image.new("RGBA", (width, height), color)
    img.save(output_path)
    print(f"Saved {output_path} ({width}×{height})")


if __name__ == "__main__":
    import pathlib

    output_dir = pathlib.Path(__file__).parent / f"images"
    output_dir.mkdir(exist_ok=True, parents=True)
    for i in range(5000):
        create_png(100, 100, output_path=str(output_dir / f"{i}.png"))
