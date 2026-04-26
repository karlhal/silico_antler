import { Cpu } from 'lucide-react'
import { Button } from '../ui/Button'
import type { Recommendation } from '../../types'

export function SurrogatePreview({
  recommendation: _recommendation,
  topRecommendation: _topRecommendation,
  isVisible: _isVisible,
  onOpenPlayground
}: {
  recommendation: Recommendation
  topRecommendation: Recommendation | null
  isVisible: boolean
  onOpenPlayground?: () => void
}) {
  return (
    <Button
      onClick={onOpenPlayground}
      className="h-9 rounded-lg px-5 text-[10px] font-bold uppercase tracking-[0.18em]"
    >
      <Cpu className="mr-2 size-3" />
      Test in AI surrogate
    </Button>
  )
}
