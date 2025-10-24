from disnake.ext import commands
import disnake
import os
from dotenv import load_dotenv
import numpy as np
from PIL import Image, ImageEnhance

# Load .env file
load_dotenv()
TOKEN = os.getenv("TOKEN")

# Discord bot setup
intents = disnake.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")


# Base directory (where main.py is located)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# === IMAGE CONVERSION LOGIC ===
def closest_tile_index(color, tile_colors):
    diffs = np.sum((tile_colors - color) ** 2, axis=1)
    return int(np.argmin(diffs))


def convert_image_to_map(input_image_path, output_dir="output"):
    theme_path = os.path.join(BASE_DIR, "BS_MAP", "Desert")

    if not os.path.exists(theme_path):
        print(f"❌ ERROR, Theme path not found: {theme_path}")
        return None

    theme_images = sorted(
        [
            img
            for img in os.listdir(theme_path)
            if img.lower().endswith((".png", ".jpg", ".jpeg"))
        ]
    )

    if not theme_images:
        print("❌ ERROR, No theme images found.")
        return None

    loaded_tiles = {}
    tile_colors = []
    tile_names = []

    for img in theme_images:
        tile = (
            Image.open(os.path.join(theme_path, img)).convert("RGBA").resize((10, 10))
        )
        arr = np.array(tile.resize((1, 1)))
        avg_color = arr[0, 0][:3]
        loaded_tiles[img] = tile
        tile_colors.append(avg_color)
        tile_names.append(img)

    tile_colors = np.array(tile_colors)
    breakable_tile = loaded_tiles.get("Breakable-Mine.png", None)

    try:
        img = Image.open(input_image_path).convert("RGBA")
    except Exception as e:
        print(f"❌ ERROR, Could not open image: {e}")
        return None

    img = ImageEnhance.Contrast(img).enhance(1.5).resize((600, 600))
    img_array = np.array(img)
    blocks = img_array.reshape(60, 10, 60, 10, 4).mean(axis=(1, 3)).astype(int)

    grid_path = os.path.join(BASE_DIR, "BS_MAP", "GRID", "grid_60x60.png")
    if os.path.exists(grid_path):
        output_img = Image.open(grid_path).convert("RGBA").resize((600, 600))
    else:
        output_img = Image.new("RGBA", (600, 600), "white")

    for y in range(60):
        for x in range(60):
            r, g, b, a = blocks[y, x]
            if a < 50:
                continue
            if np.linalg.norm([r - 255, g - 255, b - 255]) < 20 and breakable_tile:
                tile = breakable_tile
            else:
                idx = closest_tile_index(np.array([r, g, b]), tile_colors)
                tile = loaded_tiles[tile_names[idx]]
            output_img.alpha_composite(tile, (x * 10, y * 10))

    os.makedirs(output_dir, exist_ok=True)
    img_name = os.path.splitext(os.path.basename(input_image_path))[0]
    output_path = os.path.join(output_dir, f"MAP_{img_name}.png")
    output_img.convert("RGB").save(output_path)
    return output_path


# === PREFIX COMMAND ===
@bot.command()
async def convert_prefix(ctx):
    """Convert an uploaded image into a map (prefix command)."""
    if not ctx.message.attachments:
        embed = disnake.Embed(
            title="⚠️ Missing Image",
            description="Please upload an image along with your message.",
            color=disnake.Color.orange(),
        )
        await ctx.send(embed=embed)
        return

    file = ctx.message.attachments[0]
    path = f"input_{file.filename}"
    await file.save(path)

    result = convert_image_to_map(path)

    if result:
        embed_success = disnake.Embed(
            description="<:succes:1430538649136660530> Your map has been generated successfully!",
            color=disnake.Color.green(),
        )
        await ctx.send(embed=embed_success, file=disnake.File(result))

    else:
        embed_fail = disnake.Embed(
            title="❌ Conversion Failed",
            description="Something went wrong while generating your map.\nPlease ensure your image and map assets are valid.",
            color=disnake.Color.red(),
        )


@bot.slash_command(
    name="convert",
    description="Convert an uploaded image into a map (slash command).",
)
async def convert_slash(
    inter: disnake.ApplicationCommandInteraction, attachment: disnake.Attachment
):
    await inter.response.defer(with_message=True)

    path = f"input_{attachment.filename}"
    await attachment.save(path)

    result = convert_image_to_map(path)

    if result:
        embed = disnake.Embed(
            description="<:succes:1430538649136660530> Your map has been generated successfully!",
            color=disnake.Color.green(),
        )
        # ✅ Tout envoyé dans la même réponse
        await inter.edit_original_response(embed=embed, file=disnake.File(result))
    else:
        embed_fail = disnake.Embed(
            title="❌ Conversion Failed",
            description="Something went wrong while generating your map.\nPlease ensure your image and map assets are valid.",
            color=disnake.Color.red(),
        )
        await ctx.send(embed=embed_fail)
        print("❌ ERROR, Map conversion failed.")
        await inter.edit_original_response(embed=embed)
        print("❌ ERROR, Map conversion failed.")


bot.run(TOKEN)
