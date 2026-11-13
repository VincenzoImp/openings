import { useState } from "react";
import type { Json } from "../../api";
import { Button, Field, IconButton } from "../../design";
import { nextTime } from "./model";

/**
 * When a source runs: every interval, or at daily times in a time zone. The
 * values are read from the surrounding form (`scheduleValues`).
 */
export function ScheduleFields({ schedule }: { schedule?: Json }) {
  const [kind, setKind] = useState(String(schedule?.kind || "interval"));
  const [times, setTimes] = useState<string[]>(
    (schedule?.times as string[]) || ["07:00"],
  );
  return (
    <>
      <Field label="Frequency">
        <select
          name="schedule_kind"
          value={kind}
          onChange={(event) => setKind(event.target.value)}
        >
          <option value="interval">Every interval</option>
          <option value="daily">At daily times</option>
        </select>
      </Field>
      {kind === "daily" ? (
        <>
          <fieldset className="field">
            <legend>Daily times</legend>
            <div className="row">
              {times.map((value, index) => (
                <span className="row time" key={index}>
                  <input
                    className="input"
                    name="daily_times"
                    aria-label={`Daily time ${index + 1}`}
                    type="time"
                    required
                    value={value}
                    onChange={(event) =>
                      setTimes((current) =>
                        current.map((item, at) =>
                          at === index ? event.target.value : item,
                        ),
                      )
                    }
                  />
                  {times.length > 1 && (
                    <IconButton
                      icon="close"
                      label={`Remove daily time ${index + 1}`}
                      data-dirty-control="true"
                      onClick={() =>
                        setTimes((current) =>
                          current.filter((_, at) => at !== index),
                        )
                      }
                    />
                  )}
                </span>
              ))}
              <Button
                type="button"
                size="sm"
                data-dirty-control="true"
                disabled={times.length >= 12}
                onClick={() =>
                  setTimes((current) => [...current, nextTime(current)])
                }
              >
                Add a time
              </Button>
            </div>
          </fieldset>
          <Field
            label="Time zone"
            hint="An IANA time zone, such as Europe/Zurich. Times follow daylight saving changes; missed times are combined into one run."
          >
            <input
              name="timezone"
              required
              defaultValue={String(schedule?.timezone || "UTC")}
            />
          </Field>
        </>
      ) : (
        <Field
          label="Interval (minutes)"
          hint="15 to 43,200 minutes; 1,440 is once a day."
        >
          <input
            name="minutes"
            type="number"
            required
            min={15}
            max={43200}
            defaultValue={Number(schedule?.minutes || 1440)}
          />
        </Field>
      )}
    </>
  );
}
