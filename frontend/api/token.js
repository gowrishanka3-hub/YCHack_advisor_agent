import { AccessToken } from "livekit-server-sdk";
import { RoomAgentDispatch, RoomConfiguration } from "@livekit/protocol";

const AGENT_NAME = "academic-advisor";

function randomSuffix() {
  return Math.floor(1000 + Math.random() * 9000);
}

export default async function handler(req, res) {
  if (req.method !== "POST" && req.method !== "GET") {
    res.setHeader("Allow", "GET, POST");
    return res.status(405).json({ error: "Method not allowed" });
  }

  const livekitUrl = process.env.LIVEKIT_URL;
  const apiKey = process.env.LIVEKIT_API_KEY;
  const apiSecret = process.env.LIVEKIT_API_SECRET;

  if (!livekitUrl || !apiKey || !apiSecret) {
    return res.status(500).json({
      error: "LiveKit credentials not configured. Set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET in Vercel.",
    });
  }

  const body = req.method === "POST" ? req.body ?? {} : {};
  const roomName = body.room_name || `advisor_room_${randomSuffix()}`;
  const identity = body.participant_identity || `student_${randomSuffix()}`;
  const participantName = body.participant_name || "Student";

  const at = new AccessToken(apiKey, apiSecret, {
    identity,
    name: participantName,
    ttl: "15m",
  });

  at.addGrant({
    roomJoin: true,
    room: roomName,
    canPublish: true,
    canSubscribe: true,
    canPublishData: true,
  });

  if (body.room_config?.agents?.length) {
    at.roomConfig = RoomConfiguration.fromJson(body.room_config);
  } else {
    at.roomConfig = new RoomConfiguration({
      agents: [new RoomAgentDispatch({ agentName: AGENT_NAME })],
    });
  }

  const participantToken = await at.toJwt();

  return res.status(201).json({
    server_url: livekitUrl,
    participant_token: participantToken,
  });
}
