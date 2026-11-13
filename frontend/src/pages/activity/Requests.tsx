import {
  api,
  type AgentRequest,
  type ListResult,
  type RequestState,
} from "../../api";
import {
  ActorChip,
  Button,
  Card,
  Chips,
  EmptyState,
  ErrorBanner,
  Loading,
  Question,
  Tag,
  type Tone,
} from "../../design";
import { Pager } from "../../library/common";
import { dayTime } from "../../library/time";
import { useFresh } from "../../library/useFresh";
import { useUrlState } from "../../state";
import type { Act } from "./QuestionItem";
import { RunLink } from "./RunTag";
import { RequestForm } from "./RequestForm";
import { SubjectLink, useAct, type Links } from "./records";

const PAGE = 10;
const NONE: ListResult<AgentRequest> = { items: [], total: 0 };
export const requestStates: Record<
  RequestState,
  { label: string; tone: Tone; filter: string }
> = {
  open: {
    label: "Waiting for your agent",
    tone: "attention",
    filter: "Waiting",
  },
  taken: { label: "Taken by your agent", tone: "info", filter: "Taken" },
  done: { label: "Done", tone: "ready", filter: "Done" },
  declined: { label: "Declined", tone: "danger", filter: "Declined" },
  withdrawn: { label: "Withdrawn", tone: "neutral", filter: "Withdrawn" },
};

/** One request: what the owner wrote, where it stands and what the agent answered. */
export function RequestItem({
  request,
  act,
  busy,
  ...links
}: Links & { request: AgentRequest; act: Act; busy: boolean }) {
  const state = requestStates[request.state];
  const handled = request.state === "done" || request.state === "declined";
  return (
    <Question
      small
      ask={request.text}
      time={dayTime(request.created_at)}
      lead={<Tag tone={state.tone}>{state.label}</Tag>}
    >
      {handled && <p className="answered prose">{request.result}</p>}
      <p className="caption about">
        <ActorChip actor={request.created_by} /> wrote it
        {request.subject && (
          <>
            {" · about "}
            <SubjectLink subject={request.subject} {...links} />
          </>
        )}
        {request.state === "taken" && (
          <>
            {" · taken by "}
            <ActorChip actor={request.taken_by} /> {dayTime(request.taken_at)}
          </>
        )}
        {(handled || request.state === "withdrawn") && (
          <>
            {" · "}
            {request.state === "done"
              ? "completed"
              : request.state === "declined"
                ? "declined"
                : "withdrawn"}
            {" by "}
            <ActorChip actor={request.resolved_by} />{" "}
            {dayTime(request.resolved_at)}
          </>
        )}
        {request.run_id && (
          <>
            {" · "}
            <RunLink
              id={request.run_id}
              label={`${request.run_workflow || "The"} run`}
            />
          </>
        )}
      </p>
      {(request.state === "open" || request.state === "taken") && (
        <div className="answer">
          <Button
            size="sm"
            disabled={busy}
            onClick={() =>
              void act(
                () =>
                  api(`/requests/${request.id}/withdraw`, "POST", {
                    expected_version: request.version,
                  }),
                "Request withdrawn.",
              )
            }
          >
            Withdraw
          </Button>
        </div>
      )}
    </Question>
  );
}

/** Requests for the agent: write one, and follow what became of each. */
export function Requests(links: Links) {
  const [state, setState] = useUrlState("state", ""),
    [offset, setOffset] = useUrlState("offset", "0");
  const list = useFresh(
    `/requests?limit=${PAGE}&offset=${Number(offset) || 0}${state ? "&state=" + state : ""}`,
    NONE,
    ["requests"],
  );
  const { act, busy } = useAct(list.reload);
  return (
    <div className="cols aside-first">
      <Card title="Ask your agent">
        <RequestForm act={act} busy={busy} />
      </Card>
      <Card
        title="Requests"
        actions={<span className="caption num">{list.data.total}</span>}
      >
        <div className="filters">
          <Chips
            label="State"
            value={state}
            onChange={(next) => {
              setOffset("0");
              setState(next);
            }}
            options={[
              { id: "", label: "All" },
              ...Object.entries(requestStates).map(([id, item]) => ({
                id,
                label: item.filter,
              })),
            ]}
          />
        </div>
        {list.error ? (
          <div className="body">
            <ErrorBanner message={list.error} retry={list.reload} />
          </div>
        ) : list.loading ? (
          <Loading label="Loading requests…" />
        ) : list.data.items.length ? (
          list.data.items.map((request) => (
            <RequestItem
              key={request.id}
              request={request}
              act={act}
              busy={busy}
              {...links}
            />
          ))
        ) : (
          <EmptyState
            title={state ? "No requests in this state" : "No requests yet"}
          >
            {state
              ? "Choose another state to see the other requests."
              : "Write what your agent should do next. It reads open requests at the start of every run and reports the result here."}
          </EmptyState>
        )}
        <Pager
          offset={Number(offset) || 0}
          total={list.data.total}
          limit={PAGE}
          onChange={(value) => setOffset(String(value))}
          label="Request pages"
        />
      </Card>
    </div>
  );
}
