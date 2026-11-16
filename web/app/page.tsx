import { ResultsFeed } from "@/components/ResultsFeed";
import { getResults } from "@/lib/data";

export default function HomePage() {
  return (
    <>
      <h1 className="sr-only">최근 경기 결과</h1>
      <ResultsFeed briefs={getResults()} />
    </>
  );
}
