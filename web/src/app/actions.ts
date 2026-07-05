"use server";

import { BigQuery } from '@google-cloud/bigquery';

export async function getLiveSentiment() {
    try {
        const bigquery = new BigQuery({ projectId: 'vant-486316' });
        
        // Calculate composite stress index logic identical to dashboard
        const query = `
            WITH latest_weeks AS (
                SELECT DISTINCT week_start_date 
                FROM db.google_search_trends 
                ORDER BY week_start_date DESC LIMIT 2
            ),
            term_stats AS (
                SELECT 
                    search_term,
                    MIN(avg_interest_score) as min_score,
                    MAX(avg_interest_score) as max_score
                FROM db.google_search_trends
                GROUP BY search_term
            ),
            normalized AS (
                SELECT 
                    t.week_start_date,
                    t.search_term,
                    t.avg_interest_score,
                    CASE 
                        WHEN s.max_score = s.min_score THEN 0 
                        ELSE (t.avg_interest_score - s.min_score) / (s.max_score - s.min_score) 
                    END as norm_score
                FROM db.google_search_trends t
                JOIN term_stats s ON t.search_term = s.search_term
                WHERE t.week_start_date IN (SELECT week_start_date FROM latest_weeks)
            )
            SELECT 
                week_start_date,
                search_term,
                avg_interest_score,
                norm_score
            FROM normalized
            ORDER BY week_start_date DESC, search_term
        `;
        
        const [rows] = await bigquery.query({ query });
        
        if (!rows || rows.length === 0) {
            return null;
        }

        // Group by week
        const weeks = [...new Set(rows.map(r => r.week_start_date.value))].sort().reverse();
        
        const currentWeekRows = rows.filter(r => r.week_start_date.value === weeks[0]);
        const previousWeekRows = rows.filter(r => r.week_start_date.value === weeks[1]);

        const WEIGHTS: Record<string, number> = {
            'Foreclosure Auctions': 0.40,
            'Home Insurance': 0.30,
            'Estate Sales': 0.20,
            'Mortgage Assumption': 0.10,
        };

        const calcScore = (weekRows: any[]) => {
            let score = 0;
            for (const row of weekRows) {
                const weight = WEIGHTS[row.search_term] || 0;
                score += (row.norm_score * weight) * 100;
            }
            return Math.round(score);
        };

        const currentScore = calcScore(currentWeekRows);
        const prevScore = calcScore(previousWeekRows);
        
        let sentiment = "NEUTRAL";
        let color = "#aaa";
        if (currentScore >= 60) {
            sentiment = "CRITICAL";
            color = "#ff4444";
        } else if (currentScore >= 40) {
            sentiment = "ELEVATED";
            color = "#ff9944";
        } else if (currentScore >= 20) {
            sentiment = "CAUTIOUS";
            color = "#ffdd00";
        } else {
            sentiment = "STABLE";
            color = "#44ff44";
        }

        // Top 3 friction points based on highest norm_score for current week
        const sortedFriction = [...currentWeekRows]
            .sort((a, b) => b.norm_score - a.norm_score)
            .slice(0, 3)
            .map(row => {
                const severity = row.norm_score > 0.7 ? "high" : (row.norm_score > 0.4 ? "med" : "low");
                const pointColor = severity === 'high' ? '#ff4444' : (severity === 'med' ? '#ff9944' : '#44ff44');
                return {
                    label: row.search_term,
                    severity: severity,
                    color: pointColor
                };
            });

        const diff = currentScore - prevScore;
        const diffText = Math.abs(diff) + " pts WoW";
        const diffSign = diff >= 0 ? "▲" : "▼";
        const diffColor = diff > 0 ? "#ff4444" : "#44ff44";

        return {
            score: currentScore,
            sentiment,
            color,
            diffText,
            diffSign,
            diffColor,
            frictionPoints: sortedFriction
        };
    } catch (e: any) {
        console.error("Error fetching live sentiment:", e);
        return { error: e.message || String(e) };
    }
}
