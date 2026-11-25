import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { extractFromText, glossTripWords } from "./trip.ts";

const ENGLISH =
  "Four days in Dubai with my wife and daughter, AED 5,000 budget, culture and beaches, affordable hotel, relaxed pace.";

const HINDI =
  "यार एक दुबई का प्लान बनाओ चार लोगों के लिए। एक कपल है, दो बच्चे हैं और बीचस वगैरह ज्यादा विजिट करनी है।";

describe("extractFromText", () => {
  it("reads the English example", () => {
    const { patch, found } = extractFromText(ENGLISH);
    assert.equal(patch.days, 4);
    assert.equal(patch.budget, "5000");
    assert.equal(patch.budgetMode, "total");
    assert.equal(patch.who, "family");
    assert.equal(patch.adults, 2);
    assert.equal(patch.children, 1);
    assert.deepEqual(patch.interests, ["culture", "beaches"]);
    assert.equal(patch.hotel, "budget");
    assert.equal(patch.pace, "relaxed");
    assert.ok(found.includes("family trip"));
    assert.ok(found.includes("4 days"));
  });

  it("reads a couple with two children and a headcount", () => {
    const { patch } = extractFromText("A couple and two children, four people, beaches.");
    assert.equal(patch.who, "family");
    assert.equal(patch.adults, 2);
    assert.equal(patch.children, 2);
    assert.deepEqual(patch.interests, ["beaches", "family"]);
  });

  it("reads the spoken Hindi description", () => {
    const { patch, found } = extractFromText(HINDI);
    assert.equal(patch.who, "family");
    assert.equal(patch.adults, 2);
    assert.equal(patch.children, 2);
    assert.deepEqual(patch.interests, ["beaches"]);
    assert.equal(patch.days, undefined);
    assert.equal(patch.budget, undefined);
    assert.ok(found.some((item) => item.includes("2 adults") && item.includes("2 children")));
    assert.ok(found.some((item) => item.includes("beaches")));
  });

  it("reads a Hindi paraphrase of the English example", () => {
    const { patch } = extractFromText(
      "चार दिन दुबई में पत्नी और बेटी के साथ, बजट ५०००, संस्कृति और समुद्र, सस्ता होटल, आराम से।",
    );
    assert.equal(patch.days, 4);
    assert.equal(patch.budget, "5000");
    assert.equal(patch.who, "family");
    assert.equal(patch.adults, 2);
    assert.equal(patch.children, 1);
    assert.deepEqual(patch.interests, ["culture", "beaches"]);
    assert.equal(patch.hotel, "budget");
    assert.equal(patch.pace, "relaxed");
  });

  it("does not treat the Hindi word for between as a beach", () => {
    const glossed = glossTripWords("दो के बीच एक दिन");
    assert.equal(glossed.includes("beach"), false);
    const { patch } = extractFromText("दो के बीच एक दिन");
    assert.equal(patch.days, 1);
    assert.equal(patch.interests, undefined);
  });
});
