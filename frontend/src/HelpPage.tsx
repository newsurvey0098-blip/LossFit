import { Link } from 'react-router-dom';

export default function HelpPage() {
  return <>
    <p className="eyebrow">LOSSFIT SUPPORT</p>
    <h1>Help &amp; support</h1>
    <p className="muted">Quick guidance for tracking food, understanding your data, and managing your account.</p>
    <section className="card manualform">
      <h2>Log a meal</h2>
      <p>Search the food catalogue or add a private food, select a serving, then review the meal before saving. Nutrition is scaled from the selected amount; values that were not available stay marked as unknown.</p>
      <div className="actions"><Link className="button primary" to="/foods">Find food</Link><Link className="button" to="/meals/new">Create a meal</Link></div>
    </section>
    <section className="card manualform">
      <h2>Scan food</h2>
      <p>Meal and label scans are estimates. Review every detected item and serving before saving. Barcode records show their source, and you can enter a barcode manually when camera scanning is unavailable.</p>
      <p className="muted">AI scanning requires a provider configured by the LossFit operator. Without provider credentials the app reports that scanning is unavailable and manual logging remains available.</p>
      <Link className="button" to="/scan">Open scanner</Link>
    </section>
    <section className="card manualform">
      <h2>Your privacy and exports</h2>
      <p>Download your nutrition history as CSV or JSON, or delete your account after confirming your password. Deletion markers are retained separately so an older backup cannot restore a deleted account before that backup expires.</p>
      <Link className="button" to="/profile">Profile and data settings</Link>
    </section>
    <section className="card manualform">
      <h2>External sign-in</h2>
      <p>Google linking is optional and requires credentials configured by the LossFit operator. LossFit does not merge accounts based on matching email addresses.</p>
      <Link className="button" to="/settings/accounts">Connected accounts</Link>
    </section>
    <p className="muted">Nutrition information is for general wellness and is not medical advice. For personal medical guidance, speak with a qualified health professional.</p>
  </>;
}
