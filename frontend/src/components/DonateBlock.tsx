/**
 * PayPal hosted-button donate block (UAP Explorer Donation).
 * Uses the single-button "embed a payment link" variant (no PayPal JS SDK
 * required), so it works inside this SPA without any external scripts.
 * Hosted Button ID: PPTC2GVVTTXPC
 */
export default function DonateBlock({
  heading = "Support this project",
  blurb = "UAP Explorer is an independent research portal. If it's useful to you, consider chipping in for hosting and Azure AI costs. 100% optional — every record on this site is and will remain free.",
}: {
  heading?: string;
  blurb?: string;
}) {
  return (
    <section className="donate-block">
      <h3 style={{ marginTop: 0 }}>{heading}</h3>
      <p className="muted" style={{ marginBottom: 12 }}>
        {blurb}
      </p>

      <div>
        <style>{`
          .pp-PPTC2GVVTTXPC {
            text-align: center;
            border: none;
            border-radius: 0.25rem;
            min-width: 11.625rem;
            padding: 0 2rem;
            height: 2.625rem;
            font-weight: bold;
            background-color: #FFD140;
            color: #000000;
            font-family: "Helvetica Neue", Arial, sans-serif;
            font-size: 1rem;
            line-height: 1.25rem;
            cursor: pointer;
          }
        `}</style>
        <form
          action="https://www.paypal.com/ncp/payment/PPTC2GVVTTXPC"
          method="post"
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: "inline-grid",
            justifyItems: "center",
            alignContent: "start",
            gap: "0.5rem",
          }}
        >
          <input
            className="pp-PPTC2GVVTTXPC"
            type="submit"
            value="Donate"
          />
          <img
            src="https://www.paypalobjects.com/images/Debit_Credit_APM.svg"
            alt="Accepted cards"
            style={{ height: "1.25rem" }}
          />
          <section style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
            Powered by{" "}
            <img
              src="https://www.paypalobjects.com/paypal-ui/logos/svg/paypal-wordmark-color.svg"
              alt="PayPal"
              style={{ height: "0.875rem", verticalAlign: "middle" }}
            />
          </section>
        </form>
      </div>
    </section>
  );
}
