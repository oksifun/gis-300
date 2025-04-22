from api.v4.telephony.consumers.base import BaseConsumer


class MessengerConsumer(BaseConsumer):
    """Базовый класс для consumer"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = self.scope["user"]
        self.channel = f"updates_{str(self.user_id)}"
        self.channel_name = f"updates_{str(self.user_id)}"

    async def websocket_connect(self, event):
        await self.accept()
        await self.channel_layer.group_add(self.channel, self.channel_name)

        # data = UserTasks.get_notices(self.user_id)
        # await self.send_json({
        #     "type": "websocket.send",
        #     "data": dict(result=data)
        # })

    async def disconnect(self, event):
        """On disconnect exit from the group"""
        await self.channel_layer.group_discard(self.channel, self.channel_name)
        # await self.close()

    # async def get_notices(self, event):
    #     data = UserTasks.get_notices(self.user_id)
    #     print('data in get_notices', data)
    #     # await self.send_json({
    #     #     "type": "websocket.send",
    #     #     "data": dict(result=data)
    #     # })
    #
    #     # data = self.notices()
    #     await self._group_send(data=data, event=event['event'])
