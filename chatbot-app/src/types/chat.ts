export type Role = "user" | "assistant";

export interface Message {
  id: string;
  role: Role;
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  imageIds?: string[];
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  lastMessage: string;
  updatedAt: Date;
  unread?: number;
}
