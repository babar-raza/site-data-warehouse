"""
Channel implementations for insight dispatching
"""
from .base import Channel, DispatchResult
from .slack import SlackChannel
from .jira import JiraChannel
from .email import EmailChannel
from .webhook import WebhookChannel

__all__ = [
    'Channel',
    'DispatchResult',
    'SlackChannel',
    'JiraChannel',
    'EmailChannel',
    'WebhookChannel'
]
