from aiogram import BaseMiddleware, types
from aiogram.fsm.context import FSMContext


class StateCheckMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.Message, data: dict):
        state: FSMContext = data.get('state')
        current_state = await state.get_state()

        # Приоритетное выполнение команды /cancel
        if event.text.startswith('/cancel'):
            await handler(event, data)
            return

        # Проверяем, является ли сообщение командой (начинается со слеша)
        if event.text.startswith('/'):
            if current_state is None:
                await handler(event, data)
            else:
                await event.answer(
                    "Эта команда недоступна в текущем состоянии. Завершите текущую операцию или отмените её командой /cancel.")
        else:
            await handler(event, data)
