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
    
    async def ingest_chat(
        self,
        channel: str,
        duration_minutes: int,
        workspace_id: str,
        job_id: str
    ) -> dict:
        """
        Ingest Twitch chat for a specified duration, extracting entities/relations.
        
        Args:
            channel: Channel name (without #)
            duration_minutes: How long to collect chat
            workspace_id: Workspace to ingest into
            job_id: Job ID for status tracking
            
        Returns:
            Dict with entities_extracted, relations_extracted, message_count
        """
        import asyncio
        import json
        from app.document_processor import ingest_status, ingest_control
        from app.memory_store import GraphMemory
        from app.llm_config import llm_config
        from langchain_core.messages import HumanMessage
        
        channel = channel.lower().strip().lstrip('#')
        total_seconds = duration_minutes * 60
        start_time = time.time()
        
        # Initialize status with twitch_chat type
        if workspace_id not in ingest_status:
            ingest_status[workspace_id] = {}
        
        ingest_status[workspace_id][job_id] = {
            "status": "processing",
            "current": 0,
            "total": total_seconds,
            "filename": f"twitch:#{channel}",
            "type": "twitch_chat",
            "updated_at": time.time()
        }
        
        # Reset control flag
        if workspace_id in ingest_control and job_id in ingest_control[workspace_id]:
            del ingest_control[workspace_id][job_id]
        
        memory = GraphMemory(workspace_id=workspace_id)
        all_messages = []
        count_entities = 0
        count_relations = 0
        
        try:
            while True:
                elapsed = time.time() - start_time
                
                # Check if duration reached
                if elapsed >= total_seconds:
                    break
                
                # Check for cancellation
                if workspace_id in ingest_control and ingest_control[workspace_id].get(job_id) == "stop":
                    ingest_status[workspace_id][job_id]["status"] = "cancelled"
                    ingest_status[workspace_id][job_id]["updated_at"] = time.time()
                    return {
                        "entities_extracted": count_entities,
                        "relations_extracted": count_relations,
                        "message_count": len(all_messages),
                        "cancelled": True
                    }
                
                # Update progress (time-based)
                ingest_status[workspace_id][job_id]["current"] = int(elapsed)
                ingest_status[workspace_id][job_id]["updated_at"] = time.time()
                
                # Collect chat for 30 seconds
                collect_time = min(30, total_seconds - elapsed)
                if collect_time <= 0:
                    break
                    
                result = await asyncio.to_thread(
                    self.connect_and_collect,
                    channel,
                    max_tokens=2000,
                    timeout_sec=int(collect_time)
                )
                
                messages = result.get("messages", [])
                if messages:
                    all_messages.extend(messages)
                    
                    # Format messages for extraction
                    chat_text = "\n".join([
                        f"{msg['username']}: {msg['message']}" 
                        for msg in messages
                    ])
                    
                    # Extract entities and relations
                    extraction_prompt = f"""Analyze the following Twitch chat messages and extract meaningful entities and relationships.
Focus on: topics being discussed, streamers mentioned, games, events, memes, and viewer interactions.

Chat Messages:
{chat_text}

Return the output strictly as a JSON object with two keys: "entities" and "relations".

1. "entities": A list of objects {{ "name": "Exact Name", "type": "Category", "description": "Brief facts" }}
   Categories can be: Streamer, Game, Topic, Event, Meme, Viewer, etc.
2. "relations": A list of objects {{ "source": "Entity Name", "target": "Entity Name", "relation": "relationship label" }}

JSON:
"""
                    
                    try:
                        llm = llm_config.get_ingestion_llm()
                        response = await llm.ainvoke([HumanMessage(content=extraction_prompt)])
                        content = response.content
                        
                        match = re.search(r"\{.*\}", content, re.DOTALL)
                        if match:
                            data = json.loads(match.group(0))
                            
                            entities = data.get("entities", [])
                            relations = data.get("relations", [])
                            
                            for entity in entities:
                                await asyncio.to_thread(
                                    memory.add_entity,
                                    entity["name"],
                                    entity["type"],
                                    entity["description"]
                                )
                                count_entities += 1
                            
                            for rel in relations:
                                await asyncio.to_thread(
                                    memory.add_relation,
                                    rel["source"],
                                    rel["target"],
                                    rel["relation"]
                                )
                                count_relations += 1
                                
                    except Exception as e:
                        print(f"Error extracting from Twitch chat: {e}")
                
                # Small delay before next collection cycle
                await asyncio.sleep(1)
            
            # Final success status
            ingest_status[workspace_id][job_id] = {
                "status": "completed",
                "current": total_seconds,
                "total": total_seconds,
                "filename": f"twitch:#{channel}",
                "type": "twitch_chat",
                "updated_at": time.time()
            }
            
            return {
                "entities_extracted": count_entities,
                "relations_extracted": count_relations,
                "message_count": len(all_messages)
            }
            
        except Exception as e:
            ingest_status[workspace_id][job_id] = {
                "status": "error",
                "error": str(e),
                "current": int(time.time() - start_time),
                "total": total_seconds,
                "filename": f"twitch:#{channel}",
                "type": "twitch_chat",
                "updated_at": time.time()
            }
            raise e


# Global instance
twitch_service = TwitchChatService()

