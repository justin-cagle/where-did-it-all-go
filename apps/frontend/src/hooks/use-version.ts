import { useQuery } from '@tanstack/react-query'
import { isNewerVersion } from '@/domain/version'

const GITHUB_REPO = 'justin-cagle/where-did-it-all-go'

interface GitHubRelease {
  tag_name: string
  html_url: string
}

interface VersionStatus {
  current: string
  latest: string
  updateAvailable: boolean
  releaseUrl: string
}

async function fetchLatestRelease(): Promise<GitHubRelease | null> {
  try {
    const res = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/releases/latest`, {
      headers: { Accept: 'application/vnd.github+json' },
    })
    if (!res.ok) return null
    return (await res.json()) as GitHubRelease
  } catch {
    return null
  }
}

export function useVersionCheck(): { status: VersionStatus | null; isLoading: boolean } {
  const current = __APP_VERSION__
  const { data, isLoading } = useQuery({
    queryKey: ['github-latest-release'],
    queryFn: fetchLatestRelease,
    staleTime: 60 * 60 * 1000,
    retry: false,
  })

  if (!data) return { status: null, isLoading }

  return {
    status: {
      current,
      latest: data.tag_name,
      updateAvailable: isNewerVersion(current, data.tag_name),
      releaseUrl: data.html_url,
    },
    isLoading,
  }
}
