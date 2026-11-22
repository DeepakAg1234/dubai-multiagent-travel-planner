import Link from "next/link";

import { Footer } from "@/components/site/Footer";
import { Arrow, Check, Compass, Route, Sliders, Wallet } from "@/components/site/Icons";
import { Photo } from "@/components/site/Photo";
import { SiteNav } from "@/components/site/SiteNav";
import { altFor, CLOSING, HERO, INTERESTS, pick, photoForInterest } from "@/lib/images";

/** Illustrative only: shows the shape of an itinerary, not output from the planner. */
const SAMPLE = [
  {
    day: 1,
    title: "Old Dubai & Heritage",
    keys: [["al-fahidi-historical-neighbourhood"], ["dubai-creek-abra-crossing", "dubai-creek"], ["spice-souk", "gold-souk"]],
    stops: [
      ["Morning", "Al Fahidi Historical Neighbourhood"],
      ["Midday", "Dubai Creek by abra"],
      ["Afternoon", "Spice and Gold Souks"],
    ],
    tags: ["Culture", "Mostly walkable", "Low cost"],
  },
  {
    day: 2,
    title: "Downtown Icons",
    keys: [["burj-khalifa"], ["the-dubai-mall"], ["dubai-fountain", "downtown-dubai"]],
    stops: [
      ["Morning", "Burj Khalifa"],
      ["Afternoon", "The Dubai Mall"],
      ["Evening", "Dubai Fountain"],
    ],
    tags: ["Landmarks", "Ticketed", "Metro + walk"],
  },
  {
    day: 3,
    title: "Beaches & Marina",
    keys: [["jumeirah-beach"], ["dubai-marina"], ["jbr-beach"]],
    stops: [
      ["Morning", "Jumeirah Beach"],
      ["Afternoon", "Dubai Marina"],
      ["Evening", "JBR waterfront"],
    ],
    tags: ["Relaxed", "Free to enter", "Tram + walk"],
  },
  {
    day: 4,
    title: "Desert & Sunset",
    keys: [["desert", "desert-dunes"], ["museum-of-the-future"], ["palm-jumeirah"]],
    stops: [
      ["Morning", "Museum of the Future"],
      ["Afternoon", "Palm Jumeirah"],
      ["Evening", "Desert experience"],
    ],
    tags: ["Signature", "Higher cost", "Taxi or tour"],
  },
];

const BENEFITS = [
  { icon: Sliders, title: "Personal to You", text: "Recommendations shaped by your interests, dates, companions and preferred pace." },
  { icon: Route, title: "More Exploring, Less Traveling", text: "Nearby attractions are grouped logically to reduce unnecessary backtracking." },
  { icon: Wallet, title: "Budget Clarity", text: "Estimated costs organized around your budget, with each figure marked as estimated or verified." },
  { icon: Compass, title: "Flexible Plans", text: "Ask for changes and get a fresh plan without filling everything in again." },
];

export default function Landing() {
  const hero = HERO();
  const closing = CLOSING();
  return (
    <>
      <SiteNav over />
      <main id="main">
        <section className="dj-hero" aria-labelledby="hero-title">
          <Photo
            photo={hero}
            alt={altFor(hero, "Burj Khalifa and the Dubai skyline")}
            sizes="100vw"
            priority
            position="center 35%"
            label="Dubai"
          />
          <div className="dj-wrap">
            <div className="dj-hero-in dj-reveal">
              <h1 id="hero-title">Your Dubai. Your Way.</h1>
              <p className="dj-hero-sub">
                Iconic landmarks, hidden gems, unforgettable experiences. Discover a Dubai itinerary made just for you.
              </p>
              <div className="dj-hero-cta">
                <Link href="/plan" className="dj-btn">
                  Plan My Dubai Trip <Arrow width={18} height={18} />
                </Link>
                <Link href="/audit" className="dj-btn dj-btn--light">
                  Check a ChatGPT plan
                </Link>
              </div>
              <ul className="dj-values" style={{ padding: 0, margin: "8px 0 0" }}>
                {["Personalized for you", "Smart routes and schedules", "Built around your budget"].map((t) => (
                  <li key={t}>
                    <Check /> {t}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <section className="dj-section" id="explore" aria-labelledby="dream-title">
          <div className="dj-wrap">
            <div className="dj-head">
              <span className="dj-eyebrow">Explore Dubai</span>
              <h2 className="dj-h2" id="dream-title">
                What kind of Dubai are you dreaming of?
              </h2>
              <p className="dj-lede">Pick one to start. We&rsquo;ll carry it into your trip plan.</p>
            </div>
            <div className="dj-cat-grid">
              {INTERESTS.filter((i) => i.id !== "luxury" && i.id !== "hidden").map((item) => {
                const photo = photoForInterest(item.id);
                return (
                  <Link key={item.id} href={`/plan?interest=${item.id}`} className="dj-cat dj-hoverzoom" aria-label={`${item.label}: start planning`}>
                    <Photo photo={photo} alt={altFor(photo, item.label)} sizes="(max-width: 720px) 72vw, (max-width: 1100px) 50vw, 25vw" label={item.label} />
                    <span className="dj-cat-text">
                      <h3>{item.label}</h3>
                      <span>{item.blurb}</span>
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>
        </section>

        <section className="dj-section" style={{ paddingTop: 0 }} aria-labelledby="smart-title">
          <div className="dj-wrap">
            <div className="dj-head">
              <span className="dj-eyebrow">Why use this planner</span>
              <h2 className="dj-h2" id="smart-title">
                A smarter way to discover Dubai.
              </h2>
            </div>
            <div className="dj-benefits">
              {BENEFITS.map(({ icon: Icon, title, text }) => (
                <article className="dj-card dj-benefit" key={title}>
                  <span className="dj-benefit-ico">
                    <Icon />
                  </span>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="dj-section dj-band" aria-labelledby="audit-title">
          <div className="dj-wrap">
            <div className="dj-head">
              <span className="dj-eyebrow">Already have a plan?</span>
              <h2 className="dj-h2" id="audit-title">
                A chatbot can write a Dubai itinerary. It cannot prove the itinerary works.
              </h2>
              <p className="dj-lede">
                Paste a plan from ChatGPT or Claude. We check each place against our Dubai list, then the hours,
                the holiday calendar, the time between stops, and the cost in dirhams. You see what failed, and a
                version rebuilt from the places that are actually usable.
              </p>
            </div>
            <Link href="/audit" className="dj-btn">
              Check a plan <Arrow width={18} height={18} />
            </Link>
          </div>
        </section>

        <section className="dj-section dj-band" id="how" aria-labelledby="how-title">
          <div className="dj-wrap">
            <div className="dj-head">
              <span className="dj-eyebrow">How it works</span>
              <h2 className="dj-h2" id="how-title">
                Three steps to your itinerary.
              </h2>
            </div>
            <ol className="dj-steps" style={{ padding: 0, listStyle: "none" }}>
              {[
                ["1", "Tell Us About Your Trip", "Share travel dates, companions, budget and interests."],
                ["2", "We Craft Your Dubai Experience", "The planning system evaluates attractions, schedules, costs and travel logistics."],
                ["3", "Explore and Personalize", "Receive a practical itinerary and refine it to suit your preferences."],
              ].map(([n, title, text]) => (
                <li className="dj-step" key={n}>
                  <span className="dj-step-n" aria-hidden="true">
                    {n}
                  </span>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="dj-section" id="sample" aria-labelledby="sample-title">
          <div className="dj-wrap">
            <div className="dj-head">
              <span className="dj-pill dj-pill--warn dj-sample-label" style={{ justifySelf: "start" }}>
                Illustrative sample, not generated for you
              </span>
              <h2 className="dj-h2" id="sample-title">
                Four Days of Dubai Magic
              </h2>
              <p className="dj-lede">
                A glimpse of how days can be shaped. Your own itinerary uses your dates, budget and interests, with
                real timings and estimated costs.
              </p>
            </div>
            <div className="dj-days-rail">
              {SAMPLE.map((d) => (
                <article className="dj-card dj-sday" key={d.day}>
                  <div className="dj-sday-photos">
                    {d.keys.map((keys, i) => {
                      const photo = pick(...keys);
                      return (
                        <Photo
                          key={i}
                          photo={photo}
                          alt={altFor(photo, d.stops[i][1])}
                          sizes="(max-width: 720px) 80vw, 25vw"
                          label={d.stops[i][1]}
                        />
                      );
                    })}
                  </div>
                  <div className="dj-sday-body">
                    <span className="dj-eyebrow">Day {d.day}</span>
                    <h3>{d.title}</h3>
                    <ol>
                      {d.stops.map(([when, what]) => (
                        <li key={what}>
                          <b>{when}</b>
                          <span>{what}</span>
                        </li>
                      ))}
                    </ol>
                    <div className="dj-tags">
                      {d.tags.map((t) => (
                        <span className="dj-pill" key={t}>
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                </article>
              ))}
            </div>
            <div style={{ marginTop: 32, textAlign: "center" }}>
              <Link href="/plan" className="dj-btn">
                Create My Own Itinerary <Arrow width={18} height={18} />
              </Link>
            </div>
          </div>
        </section>

        <section className="dj-close" aria-labelledby="close-title">
          <Photo photo={closing} alt={altFor(closing, "Dubai at dusk")} sizes="100vw" label="" />
          <div className="dj-wrap">
            <h2 id="close-title">Dubai is waiting. Your perfect trip starts here.</h2>
            <Link href="/plan" className="dj-btn">
              Start Planning <Arrow width={18} height={18} />
            </Link>
          </div>
        </section>
      </main>
      <Footer />
      <div className="dj-sticky-cta">
        <Link href="/plan" className="dj-btn">
          Plan My Trip <Arrow width={18} height={18} />
        </Link>
      </div>
    </>
  );
}
