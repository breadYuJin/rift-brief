// template 은 페이지를 옮길 때마다 새로 그려진다. 그때 한 번 들어오는 움직임을 준다.
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="page-enter">{children}</div>;
}
