# coding: utf-8
"""
    @date: 2025-03-24
    @author: Daiheng Gao
    @description: 生成合作者头像
"""
import os
import random
import fal_client

os.environ["FAL_KEY"] = "eb0ab7f5-f009-4bd3-a613-116b5c51aa7c:062b01d43258cc53025043108b3c96c8"

def on_queue_update(update):
    if isinstance(update, fal_client.InProgress):
        for log in update.logs:
            print(log["message"])

def collaborator_image(prompt):

    if random.random() < 0.5:
        prompt = "boy"
    else:
        prompt = "girl"

    result = fal_client.subscribe(
        "fal-ai/flux-lora",
        arguments={
            "prompt": "unemployables_nft, {}".format(prompt),
            "model_name": None,
            "loras": [{
                "path": "https://v3.fal.media/files/lion/T6LoRgSZg2ozX28k2_-Nz_pytorch_lora_weights.safetensors",
                "scale": 1
            }],
            "embeddings": [],
            "image_size": {
                "width": 512,
                "height": 512
                }
        },
        with_logs=True,
        on_queue_update=on_queue_update,
    )
    print(result)
    return result

if __name__ == "__main__":
    result = collaborator_image("a girl")
    image = result['images'][0]['url']
    import pdb; pdb.set_trace()

