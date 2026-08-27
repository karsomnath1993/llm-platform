import http from "k6/http";

export const options = {
  vus: 2,
  duration: "60s",
};

export default function () {
  const prompt = `Explain Kubernetes in 50 words, request id ${Math.random()}`;

  const payload = JSON.stringify({
    prompt: prompt,
    temperature: 0.2
  });

  http.post(
    "http://localhost:8000/v1/chat",
    payload,
    {
      headers: { "Content-Type": "application/json" },
      timeout: "120s"
    }
  );
}