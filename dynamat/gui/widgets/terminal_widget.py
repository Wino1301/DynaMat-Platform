"""
DynaMat Platform - Terminal Widget
Live terminal showing application status and log messages
"""

import logging
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QHBoxLayout,
    QPushButton, QLabel, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QTextCursor, QColor

logger = logging.getLogger(__name__)


class TerminalWidget(QWidget):
    """
    Terminal widget showing live application status and messages.
    
    Features:
    - Color-coded messages by level (info, warning, error)
    - Auto-scrolling to latest messages
    - Clear and export functionality
    - Limited message history for performance
    """
    
    # Signals
    message_added = pyqtSignal(str, str)  # message, level
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.max_messages = 1000  # Limit message history
        self.message_count = 0
        
        self._setup_ui()
        self._setup_logging()
        
        # Add welcome message
        self.add_message("DynaMat Platform Terminal initialized", "info")
        
        logger.info("Terminal widget initialized")
    
    def _setup_ui(self):
        """Setup the terminal UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header_frame = QFrame()
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("Terminal")
        title_font = QFont()
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Clear button
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setMaximumWidth(60)
        self.clear_btn.clicked.connect(self.clear_terminal)
        header_layout.addWidget(self.clear_btn)
        
        layout.addWidget(header_frame)
        
        # Terminal text area
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.document().setMaximumBlockCount(self.max_messages)
        
        # Set monospace font
        font = QFont("Consolas", 9)
        if not font.exactMatch():
            font = QFont("Courier New", 9)
        self.text_edit.setFont(font)
        
        # Set terminal-like appearance
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #555;
                padding: 5px;
            }
        """)
        
        layout.addWidget(self.text_edit)
    
    def _setup_logging(self):
        """Setup logging to capture application messages"""
        # This could be extended to capture logging messages
        # For now, messages are added manually through add_message()
        pass
    
    def add_message(self, message: str, level: str = "info"):
        """
        Add a message to the terminal.
        
        Args:
            message: Message text
            level: Message level (info, warning, error, success)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Format message with timestamp
        formatted_message = f"[{timestamp}] {message}"
        
        # Get color based on level
        color = self._get_color_for_level(level)
        
        # Add to text edit with color
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # Insert colored text
        format = cursor.charFormat()
        format.setForeground(QColor(color))
        cursor.setCharFormat(format)
        cursor.insertText(formatted_message + "\n")
        
        # Auto-scroll to bottom
        self.text_edit.ensureCursorVisible()
        
        # Emit signal
        self.message_added.emit(message, level)
        
        # Increment counter
        self.message_count += 1
    
    def _get_color_for_level(self, level: str) -> str:
        """Get color code for message level"""
        colors = {
            "info": "#ffffff",      # White
            "success": "#00ff00",   # Green
            "warning": "#ffaa00",   # Orange
            "error": "#ff0000",     # Red
            "debug": "#888888"      # Gray
        }
        return colors.get(level.lower(), "#ffffff")
    
    def clear_terminal(self):
        """Clear the terminal"""
        self.text_edit.clear()
        self.message_count = 0
        self.add_message("Terminal cleared", "info")
    
    def export_log(self, filename: str):
        """Export terminal content to file"""
        try:
            with open(filename, 'w') as f:
                f.write(self.text_edit.toPlainText())
            self.add_message(f"Log exported to {filename}", "success")
        except Exception as e:
            self.add_message(f"Failed to export log: {e}", "error")