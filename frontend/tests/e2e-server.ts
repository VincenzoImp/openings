// Global setup: stop before any test if the server answering on the e2e port is
// not the one this run started (another checkout, a stale process, a port race).
export default async function checkServerIdentity() {
  const { OPENINGS_E2E_PORT: port, OPENINGS_E2E_TOKEN: token } = process.env;
  const url = `http://127.0.0.1:${port}/__e2e__/run`;
  let answer: string;
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(5000) });
    answer = response.ok ? await response.text() : `HTTP ${response.status}`;
  } catch (error) {
    answer = String(error);
  }
  if (!token || answer !== token)
    throw Error(
      `The server on port ${port} is not the one this run started ` +
        `(${url} answered "${answer.slice(0, 80)}"). ` +
        "Stop the other process or choose another OPENINGS_E2E_PORT.",
    );
}
