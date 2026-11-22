export default function SiteLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="dj">
      <a className="dj-skip" href="#main">
        Skip to content
      </a>
      {children}
    </div>
  );
}
