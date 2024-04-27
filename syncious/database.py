from tortoise import fields
from tortoise.models import Model


class VideosTable(Model):
    video_id = fields.CharField(max_length=12, null=False)
    time = fields.IntField(null=False)
    username = fields.CharField(max_length=240, null=False)

    def __str__(self) -> str:
        return f"{self.video_id} at {self.time} for {self.username}"

    class Meta:
        # Shouldn't ever conflict with a table in Invidious.
        table = "wp_syncious_videos"
        unique_together = (
            (
                "video_id",
                "username",
            ),
        )
