import socket
import random
import time
import re


class TwitchChatService:
    """Service to connect to Twitch IRC and collect chat messages."""
    
    HOST = "irc.twitch.tv"
    PORT = 6667
    
    def __init__(self):
        self.socket = None
    
    def _generate_nick(self) -> str:
        """Generate anonymous viewer nickname."""
        return f"justinfan{random.randint(10000, 99999)}"
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough: ~1 token per word)."""
        return len(text.split())
    
    def connect_and_collect(
        self, 
        channel: str, 
        max_tokens: int = 1000, 
        timeout_sec: int = 30
    ) -> dict:
        """
        Connect to a Twitch channel and collect chat messages.
        
        Args:
            channel: Channel name (without #)
            max_tokens: Stop after collecting this many tokens
            timeout_sec: Maximum time to wait for messages
            
        Returns:
            Dict with channel, messages, token_count, and collection_time
        """
        # Normalize channel name
        channel = channel.lower().strip().lstrip('#')
        
        messages = []
        total_tokens = 0
        start_time = time.time()
        
        try:
            # Create socket connection
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)  # 5 sec timeout per recv
            self.socket.connect((self.HOST, self.PORT))
            
            nick = self._generate_nick()
            
            # IRC login sequence
            self.socket.send(f"NICK {nick}\r\n".encode())
            self.socket.send(f"JOIN #{channel}\r\n".encode())
            
            # Buffer for incomplete messages
            buffer = ""
            
            while True:
                elapsed = time.time() - start_time
                
                # Check timeout
                if elapsed >= timeout_sec:
                    break
                
                # Check token limit
                if total_tokens >= max_tokens:
                    break
                
                try:
                    data = self.socket.recv(2048).decode('utf-8', errors='ignore')
                except socket.timeout:
                    continue
                
                if not data:
                    break
                
                buffer += data
                lines = buffer.split('\r\n')
                buffer = lines.pop()  # Keep incomplete line in buffer
                
                for line in lines:
                    if not line:
                        continue
                    
                    # Handle PING/PONG
                    if line.startswith('PING'):
                        self.socket.send("PONG :tmi.twitch.tv\r\n".encode())
                        continue
                    
                    # Parse PRIVMSG (chat messages)
                    # Format: :username!username@username.tmi.twitch.tv PRIVMSG #channel :message
                    if 'PRIVMSG' in line:
                        match = re.match(
                            r'^:(\w+)!.*?PRIVMSG\s+#\w+\s+:(.+)$', 
                            line
                        )
                        if match:
                            username = match.group(1)
                            message_text = match.group(2).strip()
                            
                            msg_tokens = self._estimate_tokens(message_text)
                            total_tokens += msg_tokens
                            
                            messages.append({
                                "username": username,
                                "message": message_text,
                                "tokens": msg_tokens
                            })
            
            collection_time = time.time() - start_time
            
            return {
                "channel": channel,
                "messages": messages,
                "message_count": len(messages),
                "token_count": total_tokens,
                "collection_time_sec": round(collection_time, 2)
            }
            
        except Exception as e:
            return {
                "channel": channel,
                "messages": messages,
                "message_count": len(messages),
                "token_count": total_tokens,
                "collection_time_sec": round(time.time() - start_time, 2),
                "error": str(e)
            }
        finally:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
                self.socket = None
    
    def format_chat_transcript(self, result: dict) -> str:
        """Format collected messages as a readable transcript."""
        if not result.get("messages"):
            if result.get("error"):
                return f"Failed to collect chat from #{result['channel']}: {result['error']}"
            return f"No messages collected from #{result['channel']} in {result['collection_time_sec']}s"
        
        lines = [
            f"## Twitch Chat: #{result['channel']}",
            f"*Collected {result['message_count']} messages (~{result['token_count']} tokens) in {result['collection_time_sec']}s*",
            "",
            "---",
            ""
        ]
        
        for msg in result["messages"]:
            lines.append(f"**{msg['username']}**: {msg['message']}")
        
        return "\n".join(lines)


# Global instance
twitch_service = TwitchChatService()
