import { PRESETS, type Overrides } from "@/lib/compose";

type Props = {
  text: string;
  overrides: Overrides;
  live: boolean;
  busy: boolean;
  onText: (value: string) => void;
  onOverrides: (value: Overrides) => void;
  onLive: (value: boolean) => void;
  onSubmit: () => void;
};

export function InputPanel(props: Props) {
  const { overrides } = props;
  return (
    <form
      className="card reserve"
      onSubmit={(event) => {
        event.preventDefault();
        props.onSubmit();
      }}
    >
      <h2>Where to?</h2>
      <label>
        Request
        <textarea
          value={props.text}
          onChange={(event) => props.onText(event.target.value)}
          placeholder="4 days in Dubai, culture, food, and beaches, AED 5000, affordable hotel"
          name="request"
        />
      </label>
      <div className="presets" role="group" aria-label="Demo presets">
        {PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            title={preset.detail}
            onClick={() => {
              props.onText(preset.text);
              props.onOverrides(preset.overrides);
            }}
          >
            {preset.label}
          </button>
        ))}
      </div>
      <div className="fields">
        <label>
          Days
          <input
            inputMode="numeric"
            placeholder="From the request"
            value={overrides.days}
            onChange={(event) => props.onOverrides({ ...overrides, days: event.target.value })}
          />
        </label>
        <label>
          Budget AED
          <input
            inputMode="decimal"
            placeholder="From the request"
            value={overrides.budget}
            onChange={(event) => props.onOverrides({ ...overrides, budget: event.target.value })}
          />
        </label>
        <label>
          Start date
          <input
            type="date"
            value={overrides.startDate}
            onChange={(event) => props.onOverrides({ ...overrides, startDate: event.target.value })}
          />
        </label>
        <label>
          Hotel tier
          <select
            value={overrides.hotelTier}
            onChange={(event) => props.onOverrides({ ...overrides, hotelTier: event.target.value })}
          >
            <option value="">From the request</option>
            <option value="budget">Budget</option>
            <option value="mid">Mid</option>
            <option value="luxury">Luxury</option>
          </select>
        </label>
        <label>
          Interests
          <input
            value={overrides.interests}
            placeholder="culture food beaches"
            onChange={(event) => props.onOverrides({ ...overrides, interests: event.target.value })}
          />
        </label>
        <label>
          Pace
          <select
            value={overrides.avoidCrowds ? "quiet" : "any"}
            onChange={(event) => props.onOverrides({ ...overrides, avoidCrowds: event.target.value === "quiet" })}
          >
            <option value="any">Any crowd level</option>
            <option value="quiet">Avoid crowds</option>
          </select>
        </label>
      </div>
      <div className="checks">
        <label>
          <input
            type="checkbox"
            checked={props.live}
            onChange={(event) => props.onLive(event.target.checked)}
          />
          Live APIs
        </label>
      </div>
      <button className="primary" type="submit" disabled={props.busy || !props.text.trim()}>
        {props.busy ? "Planning…" : "Plan the trip"}
      </button>
    </form>
  );
}
