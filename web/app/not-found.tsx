import Link from "next/link";

export default function NotFound() {
  return (
    <p className="empty">
      찾는 페이지가 없습니다. <Link href="/">최근 경기 결과로 돌아가기</Link>
    </p>
  );
}
