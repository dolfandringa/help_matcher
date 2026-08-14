import { useEffect, useMemo, useRef, useState } from "react";
import { Alert, AppBar, Box, Button, Paper, Stack, TextField, Toolbar, Typography } from "@mui/material";
import { sendLocalWhatsAppMessage, websocketUrl } from "./api";

type LocalMessage = {
  direction: "incoming" | "outgoing" | "system";
  timestamp: string;
  message_id?: string;
  sender_name?: string;
  from_bsuid?: string;
  contact_name?: string;
  phone_number?: string;
  to?: string;
  text: string;
};

function buildMetaWebhookPayload({
  bsuid,
  phoneNumber,
  profileName,
  text,
}: {
  bsuid: string;
  phoneNumber: string;
  profileName: string;
  text: string;
}) {
  const messageId = `local-message-${Date.now()}`;
  return {
    object: "whatsapp_business_account",
    entry: [
      {
        id: "local-whatsapp-business-account",
        changes: [
          {
            field: "messages",
            value: {
              messaging_product: "whatsapp",
              metadata: {
                display_phone_number: "local-help-matcher",
                phone_number_id: "local-phone-number-id",
              },
              contacts: [
                {
                  profile: { name: profileName },
                  wa_id: phoneNumber || bsuid,
                },
              ],
              messages: [
                {
                  from: bsuid,
                  id: messageId,
                  timestamp: Math.floor(Date.now() / 1000).toString(),
                  type: "text",
                  text: { body: text },
                },
              ],
            },
          },
        ],
      },
    ],
  };
}

export function LocalWhatsAppPage() {
  const [bsuid, setBsuid] = useState("573001234567");
  const [phoneNumber, setPhoneNumber] = useState("573001234567");
  const [profileName, setProfileName] = useState("Local demo user");
  const [text, setText] = useState("");
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const conversationRef = useRef<HTMLDivElement>(null);
  const socketUrl = useMemo(() => websocketUrl(`/local/whatsapp/ws/${encodeURIComponent(bsuid)}`), [bsuid]);

  useEffect(() => {
    const socket = new WebSocket(socketUrl);
    socket.onmessage = (event) => {
      setMessages((currentMessages) => [...currentMessages, JSON.parse(event.data) as LocalMessage]);
    };
    socket.onerror = () => setError("Could not connect to the local WhatsApp websocket.");
    return () => socket.close();
  }, [socketUrl]);

  useEffect(() => {
    conversationRef.current?.scrollTo({ top: conversationRef.current.scrollHeight });
  }, [messages]);

  const sendMessage = async () => {
    const messageText = text.trim();
    if (!messageText) {
      return;
    }
    setText("");
    setError(null);
    try {
      await sendLocalWhatsAppMessage(
        buildMetaWebhookPayload({
          bsuid,
          phoneNumber,
          profileName,
          text: messageText,
        }),
      );
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Sending local WhatsApp message failed.");
    }
  };

  return (
    <Box className="app-shell local-whatsapp-shell">
      <AppBar position="static" color="inherit" elevation={0}>
        <Toolbar>
          <Typography variant="h6" fontWeight={800}>
            Local WhatsApp simulator
          </Typography>
        </Toolbar>
      </AppBar>
      <Box component="main" className="local-whatsapp-layout">
        <Paper className="local-whatsapp-settings" elevation={2}>
          <Stack spacing={2}>
            <Typography variant="h6" fontWeight={700}>
              Fake WhatsApp user
            </Typography>
            <TextField label="WhatsApp BSUID" value={bsuid} onChange={(event) => setBsuid(event.target.value)} />
            <TextField label="Phone number / wa_id" value={phoneNumber} onChange={(event) => setPhoneNumber(event.target.value)} />
            <TextField label="Profile name" value={profileName} onChange={(event) => setProfileName(event.target.value)} />
            <Typography variant="body2" color="text.secondary">
              Messages are sent as Meta-shaped webhook payloads to <code>/local/whatsapp/webhook</code>. Bot replies sent through
              the fake Graph endpoint appear in this conversation.
            </Typography>
          </Stack>
        </Paper>
        <Paper className="local-whatsapp-chat" elevation={2}>
          <Box ref={conversationRef} className="local-whatsapp-messages">
            {messages.map((message, index) => (
              <Box key={`${message.message_id ?? message.timestamp}-${index}`} className={`chat-bubble ${message.direction}`}>
                <Typography variant="caption" color="text.secondary">
                  {message.direction === "incoming"
                    ? message.contact_name || message.from_bsuid
                    : message.sender_name || message.direction}
                </Typography>
                <Typography>{message.text}</Typography>
              </Box>
            ))}
          </Box>
          {error ? <Alert severity="error">{error}</Alert> : null}
          <Box
            component="form"
            className="local-whatsapp-input"
            onSubmit={(event) => {
              event.preventDefault();
              void sendMessage();
            }}
          >
            <TextField
              fullWidth
              label="Message"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Necesito ayuda en..."
            />
            <Button type="submit" variant="contained" size="large">
              Send
            </Button>
          </Box>
        </Paper>
      </Box>
    </Box>
  );
}
