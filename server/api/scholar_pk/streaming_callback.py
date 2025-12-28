"""
Streaming Callback Module

This module provides functions for handling streaming callbacks in scholar analysis.
"""

import logging
from typing import Callable
from server.api.scholar.utils import create_state_message
from server.utils.stream_protocol import format_stream_message

# 获取日志记录器
logger = logging.getLogger('server.api.scholar_pk.streaming_callback')

class StreamingCallback:
    """A class to handle streaming callbacks for scholar analysis."""

    def __init__(self, yield_func: Callable, researcher_index: int):
        """Initialize the streaming callback.

        Args:
            yield_func: Function to yield messages to the stream
            researcher_index: Index of the researcher (1 or 2) for message formatting
        """
        self.yield_func = yield_func
        self.researcher_index = researcher_index
        self.researcher_prefix = f"Researcher {researcher_index}: "

    def __call__(self, msg):
        """Process a message from scholar analysis and yield it to the stream.

        Args:
            msg: Message from scholar analysis process
        """
        try:
            formatted_msg = None

            if isinstance(msg, str):
                # 如果是字符串，直接创建状态消息
                state_msg = create_state_message(f"{self.researcher_prefix}{msg}")
                formatted_msg = format_stream_message(state_msg)
            elif isinstance(msg, dict) and 'message' in msg:
                # 如果是字典并且包含message字段，则提取消息内容和进度信息
                message_content = msg['message']
                progress = msg.get('progress')  # 获取进度信息（如果存在）

                # 创建带有进度信息的状态消息
                state_msg = create_state_message(f"{self.researcher_prefix}{message_content}")

                # 如果有进度信息，添加到状态消息中
                if progress is not None:
                    state_msg['progress'] = progress

                formatted_msg = format_stream_message(state_msg)
            else:
                # 其他情况，尝试转换为字符串
                state_msg = create_state_message(f"{self.researcher_prefix}{str(msg)}")
                formatted_msg = format_stream_message(state_msg)

            # 将格式化后的消息发送到流
            if formatted_msg:
                self.yield_func(formatted_msg)

        except Exception as e:
            # 如果处理回调消息时出错，记录错误但不中断流程
            logger.error(f"Error in scholar analysis callback: {str(e)}")

        # 回调函数不需要返回值
        return None

def create_streaming_callback(researcher_index: int):
    """Create a callback function for scholar analysis that can be used with a generator.

    Args:
        researcher_index: Index of the researcher (1 or 2) for message formatting

    Returns:
        A tuple of (callback_function, message_processor)
    """
    # 创建一个列表，用于存储状态消息
    messages = []

    # 定义回调函数
    def callback(msg):
        """回调函数，用于处理状态消息"""
        try:
            # 确定研究者标识（用于消息前缀）
            researcher_prefix = f"Researcher {researcher_index}: "

            if isinstance(msg, str):
                # 如果是字符串，直接创建状态消息
                state_msg = create_state_message(f"{researcher_prefix}{msg}")
                formatted_msg = format_stream_message(state_msg)
                messages.append(formatted_msg)
            elif isinstance(msg, dict) and 'message' in msg:
                # 如果是字典并且包含message字段，则提取消息内容和进度信息
                message_content = msg['message']
                progress = msg.get('progress')  # 获取进度信息（如果存在）

                # 创建带有进度信息的状态消息
                state_msg = create_state_message(f"{researcher_prefix}{message_content}")

                # 如果有进度信息，添加到状态消息中
                if progress is not None:
                    state_msg['progress'] = progress

                formatted_msg = format_stream_message(state_msg)
                messages.append(formatted_msg)
            else:
                # 其他情况，尝试转换为字符串
                state_msg = create_state_message(f"{researcher_prefix}{str(msg)}")
                formatted_msg = format_stream_message(state_msg)
                messages.append(formatted_msg)
        except Exception as e:
            # 如果处理回调消息时出错，记录错误但不中断流程
            logger.error(f"Error in scholar analysis callback: {str(e)}")

    # 定义获取消息函数
    def get_messages():
        """获取所有消息并清空消息列表"""
        result = list(messages)  # 创建消息列表的副本
        messages.clear()  # 清空原始消息列表
        return result

    return callback, get_messages


class RealTimeStreamingCallback:
    """A class to handle real-time streaming callbacks for scholar analysis."""

    def __init__(self, researcher_index: int, generator_func):
        """Initialize the real-time streaming callback.

        Args:
            researcher_index: Index of the researcher (1 or 2) for message formatting
            generator_func: The generator function that will yield messages
        """
        self.researcher_index = researcher_index
        self.researcher_prefix = f"Researcher {researcher_index}: "
        self.generator_func = generator_func

    def __call__(self, msg):
        """Process a message from scholar analysis and yield it to the stream.

        Args:
            msg: Message from scholar analysis process
        """
        try:
            formatted_msg = None

            if isinstance(msg, str):
                # 如果是字符串，直接创建状态消息
                state_msg = create_state_message(f"{self.researcher_prefix}{msg}")
                formatted_msg = format_stream_message(state_msg)
            elif isinstance(msg, dict) and 'message' in msg:
                # 如果是字典并且包含message字段，则提取消息内容和进度信息
                message_content = msg['message']
                progress = msg.get('progress')  # 获取进度信息（如果存在）

                # 创建带有进度信息的状态消息
                state_msg = create_state_message(f"{self.researcher_prefix}{message_content}")

                # 如果有进度信息，添加到状态消息中
                if progress is not None:
                    state_msg['progress'] = progress

                formatted_msg = format_stream_message(state_msg)
            else:
                # 其他情况，尝试转换为字符串
                state_msg = create_state_message(f"{self.researcher_prefix}{str(msg)}")
                formatted_msg = format_stream_message(state_msg)

            # 将格式化后的消息发送到流
            if formatted_msg:
                self.generator_func(formatted_msg)

        except Exception as e:
            # 如果处理回调消息时出错，记录错误但不中断流程
            logger.error(f"Error in scholar analysis callback: {str(e)}")

        # 回调函数不需要返回值
        return None
