/**
 * Job Search Tools Extension for the JobSearch agent
 *
 * Registers a `search_jobs` tool that uses the Exa search engine
 * (same backend as web_search) to search job boards and return
 * real job listings with:
 * - Title, company, location
 * - Salary range (when listed)
 * - Description snippet
 * - Apply link
 *
 * Falls back to generating web_search queries if Exa fails.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

interface JobListing {
	title: string;
	company: string;
	location: string;
	salary: string;
	description: string;
	url: string;
	source: string;
}

export default function (pi: ExtensionAPI) {
	pi.registerTool({
		name: "search_jobs",
		label: "Search Jobs",
		description:
			"Searches job boards (LinkedIn, Indeed, Google Jobs, Wellfound) and returns actual job listings with title, company, location, salary range, description snippet, and apply link. Use this for job hunting.",
		parameters: Type.Object({
			query: Type.String({
				description: "Job search query, e.g. 'KDB developer' or 'Golang backend engineer'",
			}),
			location: Type.Optional(
				Type.String({ description: "Location filter, e.g. 'Remote' or 'New York, NY'. Default: nationwide." }),
			),
		}),

		async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
			const query = params.query;
			const location = params.location || "";
			const errors: string[] = [];

			// Build targeted search queries for each major job board
			const boardSearches = [
				`site:linkedin.com/jobs ${query} ${location}`,
				`site:indeed.com ${query} ${location} salary`,
				`site:ziprecruiter.com ${query} ${location}`,
				`site:glassdoor.com/jobs ${query} ${location}`,
				`site:dice.com/jobs ${query} ${location}`,
				`site:wellfound.com ${query} ${location}`,
				`${query} ${location} job salary US`.trim(),
			];

			// Try Exa search first (same backend as web_search)
			try {
				const { searchWithExa } = await import(
					"/Users/ponzi/.pi/agent/npm/node_modules/pi-web-access/exa.js"
				);

				const allResults: JobListing[] = [];

				for (const searchQuery of boardSearches) {
					try {
						const exaResult = await searchWithExa(searchQuery, {
							numResults: 5,
							includeContent: true,
						});

						if (exaResult && "results" in exaResult && exaResult.results) {
							for (const r of exaResult.results) {
								if (r.title && r.url) {
									allResults.push({
										title: r.title,
										company: extractCompany(r.title, r.text || ""),
										location: location || extractLocation(r.text || ""),
										salary: extractSalary(r.text || ""),
										description: (r.text || "").substring(0, 400),
										url: r.url,
										source: new URL(r.url).hostname.replace("www.", ""),
									});
								}
							}
						}
					} catch {
						// Try next query
					}
				}

				// Deduplicate by URL
				const seen = new Set<string>();
				const uniqueResults = allResults.filter((r) => {
					if (seen.has(r.url)) return false;
					seen.add(r.url);
					return true;
				});

				if (uniqueResults.length > 0) {
					return formatResults(uniqueResults, query, location, errors);
				}
			} catch (e: any) {
				errors.push(`Exa: ${e.message}`);
			}

			// Fallback: return web_search queries for the LLM to execute
			return {
				content: [
					{
						type: "text",
						text:
							`## Direct search unavailable\n\n` +
							`Could not search automatically. Please use \`web_search\` with these queries:\n\n` +
							[
					`site:linkedin.com/jobs ${query} ${location}`,
					`site:indeed.com ${query} ${location} salary`,
					`site:ziprecruiter.com ${query} ${location}`,
					`site:glassdoor.com/jobs ${query} ${location}`,
					`site:dice.com/jobs ${query} ${location}`,
				].map((q) => `- \`${q}\``).join("\n") +
							(errors.length > 0 ? `\n\n**Errors:** ${errors.join("; ")}` : ""),
					},
				],
				details: { results: [], errors, fallback: true, suggestedQueries: boardSearches },
			};
		},
	});

	// Also register a simpler tool that reads a job listing page for full details
	pi.registerTool({
		name: "job_details",
		label: "Job Details",
		description:
			"Fetch full details for a specific job listing URL. Returns expanded description, requirements, and salary if available.",
		parameters: Type.Object({
			url: Type.String({ description: "URL of the job listing to fetch details for" }),
		}),

		async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
			try {
				const response = await fetch(params.url, {
					signal: AbortSignal.timeout(10_000),
					headers: {
						"User-Agent":
							"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
					},
				});

				const text = await response.text();
				const cleaned = text
					.replace(/<script[\s\S]*?<\/script>/g, "")
					.replace(/<style[\s\S]*?<\/style>/g, "")
					.replace(/<[^>]+>/g, " ")
					.replace(/\s+/g, " ")
					.trim()
					.substring(0, 3000);

				return {
					content: [{ type: "text", text: `## Job Details\n\n${cleaned}\n\n**Source:** ${params.url}` }],
					details: { url: params.url },
				};
			} catch (e: any) {
				return {
					content: [
						{
							type: "text",
							text: `Could not fetch details for ${params.url}: ${e.message}\n\nTry using \`fetch_content\` tool instead.`,
						},
					],
					details: { error: e.message, url: params.url },
				};
			}
		},
	});

	function formatResults(
	results: JobListing[],
	query: string,
	location: string,
	errors: string[],
) {
	let text = `## 📋 ${results.length} Job Listings for "${query}"${location ? ` in ${location}` : ""}\n\n`;

	for (let i = 0; i < Math.min(results.length, 15); i++) {
		const job = results[i];
		text += `### ${i + 1}. ${job.title}\n`;
		text += `**Company:** ${job.company}\n`;
		text += `**Location:** ${job.location}\n`;
		text += `**Salary:** ${job.salary}\n`;
		text += `**Source:** ${job.source}\n`;
		text += `**Description:** ${job.description.substring(0, 350)}${job.description.length > 350 ? "..." : ""}\n`;
		text += `**Apply:** ${job.url}\n\n`;
	}

	if (results.length > 15) {
		text += `*... and ${results.length - 15} more listings*\n\n`;
	}

	if (errors.length > 0) {
		text += `\n**⚠️ Note:** ${errors.join("; ")}\n`;
	}

	text +=
		`\n> 💡 **Tip:** Tell me which listing number to explore further and I'll fetch the full description and salary details.`;

	return {
		content: [{ type: "text", text }],
		details: {
			results,
			errors,
			totalResults: results.length,
		},
	};
}

	// Register a tool that verifies a job posting is still active and accepting applicants.
	// Fetches the URL, looks for active/closed signals in the page text,
	// returns a structured verdict so the agent can confidently include or exclude the listing.
	pi.registerTool({
		name: "verify_job",
		label: "Verify Job Status",
		description:
			"Verify a job posting URL is still active and accepting applicants. " +
			"Fetches the page and analyzes content for active signals (Apply now, Posted X days ago) " +
			"and closed signals (No longer accepting, Position filled, Expired, 404). " +
			"Returns a structured status: ACTIVE, CLOSED, or UNCERTAIN with the signals found.",
		parameters: Type.Object({
			url: Type.String({ description: "URL of the job posting to verify" }),
		}),

		async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
			const url = params.url;

			// Phrases that indicate the job is still active
			const ACTIVE_SIGNALS = [
				/apply\s+(?:now|today|here|on\s+this)/i,
				/(?:easy|quick)\s+apply/i,
				/apply\s+for\s+this\s+(?:job|position|role)/i,
				/submit\s+(?:your\s+)?(?:application|resume|cv)/i,
				/posted\s+(?:\d+\s+(?:day|hour|week|month)s?\s+ago|just\s+now|recently)/i,
				/(?:actively\s+)?hiring/i,
				/(?:job|position)\s+(?:is\s+)?open/i,
				/now\s+hiring/i,
				/join\s+(?:us|our\s+team)/i,
			];

			// Phrases that indicate the job is no longer active
			const CLOSED_SIGNALS = [
				/no\s+longer\s+(?:accepting|accepting\s+applications|taking\s+applications)/i,
				/(?:position|job|role)\s+(?:has\s+been\s+)?(?:filled|closed)/i,
				/(?:applications?|posting)\s+(?:are\s+)?closed/i,
				/(?:this\s+)?(?:job|position|posting)\s+(?:has\s+)?expired/i,
				/(?:not|no\s+longer)\s+available/i,
				/(?:job|position)\s+has\s+been\s+removed/i,
			];

			// HTTP status signals (LinkedIn/Indeed return specific patterns when listings are gone)
			const HTTP_CLOSED = [
				/this\s+job\s+(?:is\s+)?no\s+longer\s+available/i,
				/this\s+page\s+doesn[’'`]t\s+exist/i,
				/page\s+not\s+found/i,
				/job\s+not\s+found/i,
				/404[\s-]*(?:not\s+found|error)?/i,
			];

			try {
				const response = await fetch(url, {
					headers: {
						"User-Agent":
							"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
					},
					signal: AbortSignal.timeout(10_000),
					redirect: "follow",
				});

				// HTTP error codes
				if (response.status === 404 || response.status === 410) {
					return {
						content: [{
							type: "text",
							text: `❌ CLOSED (HTTP ${response.status}) — ${url}\nThe page returned a ${response.status} error. Job is definitely no longer available.`,
						}],
						details: { status: "CLOSED", httpCode: response.status, url, signals: [`http_${response.status}`] },
					};
				}
				if (!response.ok) {
					return {
						content: [{
							type: "text",
							text: `⚠️ UNCERTAIN (HTTP ${response.status}) — ${url}\nUnexpected response code. Page may or may not have the listing.`,
						}],
						details: { status: "UNCERTAIN", httpCode: response.status, url, signals: [`http_${response.status}`] },
					};
				}

				const text = await response.text();

				// Strip HTML tags for plain-text analysis
				const cleaned = text
					.replace(/<script[\s\S]*?<\/script>/gi, " ")
					.replace(/<style[\s\S]*?<\/style>/gi, " ")
					.replace(/<noscript[\s\S]*?<\/noscript>/gi, " ")
					.replace(/<[^>]+>/g, " ")
					.replace(/\s+/g, " ")
					.trim();

				// Collect matched signals
				const activeMatches: string[] = [];
				const closedMatches: string[] = [];

				for (const pat of ACTIVE_SIGNALS) {
					const m = cleaned.match(pat);
					if (m) activeMatches.push(m[0].trim());
				}
				for (const pat of CLOSED_SIGNALS) {
					const m = cleaned.match(pat);
					if (m) closedMatches.push(m[0].trim());
				}
				for (const pat of HTTP_CLOSED) {
					const m = cleaned.match(pat);
					if (m) closedMatches.push(m[0].trim());
				}

				// Determine status
				let status: "ACTIVE" | "CLOSED" | "UNCERTAIN" = "UNCERTAIN";
				if (closedMatches.length > 0) {
					status = "CLOSED";
				} else if (activeMatches.length >= 1) {
					status = "ACTIVE";
				}

				const summary =
					status === "ACTIVE"
						? `✅ ACTIVE — ${url}\nActive signals found: ${activeMatches.slice(0, 3).join(" | ")}`
						: status === "CLOSED"
						? `❌ CLOSED — ${url}\nClosed signals found: ${closedMatches.slice(0, 3).join(" | ")}\nDO NOT include this in results.`
						: `⚠️ UNCERTAIN — ${url}\nNo definitive signals found. Page loaded but couldn't confirm if job is still accepting.`;

				return {
					content: [{ type: "text", text: summary }],
					details: {
						status,
						url,
						activeSignals: activeMatches,
						closedSignals: closedMatches,
					},
				};
			} catch (e: any) {
				return {
					content: [{
						type: "text",
						text: `⚠️ UNCERTAIN — ${url}\nError verifying: ${e.message}\nCould not confirm status.`,
					}],
					details: { status: "UNCERTAIN", error: e.message, url, signals: [] },
				};
			}
		},
	});

	// Also register a tool to track seen jobs (prevents repeats across runs)
	pi.registerTool({
		name: "track_jobs",
		label: "Track Jobs",
		description:
			"Reads/writes the seen-jobs.json file so the agent remembers which jobs it already showed. " +
			"Call with action='read' before searching to get seen URLs, then with action='add' after presenting new jobs to record them.",
		parameters: Type.Object({
			action: Type.String({
				description: "'read' to get seen URLs, 'add' to record new job URLs",
			}),
			urls: Type.Optional(
				Type.Array(Type.String(), { description: "Job URLs to record (required for action='add')" }),
			),
		}),

		async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
			const filePath =
				"/Users/ponzi/dev/pi_agents/agents/jobsearch/references/seen-jobs.json";

			if (params.action === "read") {
				try {
					const fs = await import("node:fs");
					if (!fs.existsSync(filePath)) {
						return {
							content: [{ type: "text", text: "No seen jobs yet." }],
							details: { urls: [] },
						};
					}
					const data = JSON.parse(fs.readFileSync(filePath, "utf-8"));
					const urls: string[] = Array.isArray(data) ? data : [];
					const count = urls.length;
					return {
						content: [
							{
								type: "text",
								text:
									count > 0
										? `${count} previously seen jobs. Filter these out from new results to avoid repeats.`
										: "No previously seen jobs. All results are fresh.",
							},
						],
						details: { urls, count },
					};
				} catch (e: any) {
					return {
						content: [{ type: "text", text: `Error reading seen jobs: ${e.message}` }],
						details: { urls: [], error: e.message },
					};
				}
			}

			if (params.action === "add") {
				const newUrls: string[] = params.urls || [];
				if (newUrls.length === 0) {
					return {
						content: [{ type: "text", text: "No URLs provided to record." }],
						details: { urls: [] },
					};
				}

				try {
					const fs = await import("node:fs");
					let existing: string[] = [];
					if (fs.existsSync(filePath)) {
						try {
							existing = JSON.parse(fs.readFileSync(filePath, "utf-8"));
						} catch {
							existing = [];
						}
					}

					// Deduplicate
					const seen = new Set(existing);
					let added = 0;
					for (const url of newUrls) {
						if (!seen.has(url)) {
							seen.add(url);
							added++;
						}
					}

					const updated = Array.from(seen);
					fs.writeFileSync(filePath, JSON.stringify(updated, null, 2));

					return {
						content: [
							{
								type: "text",
								text: `Recorded ${added} new job(s). Total in memory: ${updated.length}.`,
							},
						],
						details: { urls: updated, added, total: updated.length },
					};
				} catch (e: any) {
					return {
						content: [{ type: "text", text: `Error saving seen jobs: ${e.message}` }],
						details: { error: e.message },
					};
				}
			}

			return {
				content: [{ type: "text", text: "Unknown action. Use 'read' or 'add'." }],
				details: {},
			};
		},
	});
}

function extractCompany(title: string, text: string): string {
	// Try to find company name in the text (often after "at" in title)
	const atMatch = title.match(/\bat\s+([A-Z][A-Za-z0-9\s.&]+)/);
	if (atMatch) return atMatch[1].trim();

	// Fallback: first line of description might be the company
	const lines = text.split("\n").filter((l) => l.trim());
	for (const line of lines.slice(0, 3)) {
		if (line.length < 80 && /^[A-Z][A-Za-z0-9\s.&]+$/.test(line.trim())) {
			return line.trim();
		}
	}
	return "See listing";
}

function extractLocation(text: string): string {
	const locPatterns = [
		/(?:location|loc):\s*([^\n,]+(?:,\s*[A-Z]{2})?)/i,
		/(?:remote|hybrid|on-site|onsite)[,\s]+([A-Z][A-Za-z\s]+(?:,\s*[A-Z]{2})?)/i,
		/\b(Remote|Hybrid|On-Site|Onsite)\b/i,
	];
	for (const pat of locPatterns) {
		const m = text.match(pat);
		if (m) return m[1] || m[0] || "See listing";
	}
	return "See listing";
}

function extractSalary(text: string): string {
	const salaryPatterns = [
		/\$\d{2,3}[kK]?\s*[-–to]+\s*\$\d{2,3}[kK]?/,
		/\$\d{2,3}[kK]?\s*-\s*\$\d{2,3}[kK]?/,
		/\$\d{2,3}[kK]?\s*(?:plus|\+)/,
		/(?:salary|pay|compensation|range)[:\s]*\$[\d,.kK\s-]+/i,
		/\d{2,3}[kK]\s*[-–to]+\s*\d{2,3}[kK]/,
	];
	for (const pat of salaryPatterns) {
		const m = text.match(pat);
		if (m) return m[0].trim();
	}
	return "Not listed";
}
