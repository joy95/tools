def generate_video(input_payload: dict) -> dict:
    return {
        "message": "基础图文生成视频链路已完成",
        "template_id": input_payload.get("template_id", "default"),
        "source": input_payload,
    }
