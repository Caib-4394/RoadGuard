"""Live maintenance planning dashboard for RoadGuard."""

from collections import Counter
from datetime import datetime

import pandas as pd
import streamlit as st

from core.priority import (
    DEFAULT_WORKERS_PER_CREW,
    assign_contractors,
    build_maintenance_plan,
    build_monthly_schedule,
    budget_summary_by_priority,
    estimated_completion_days,
    schedule_repair_plan,
)
from db.database import (
    query_all_detections,
    query_all_images,
    query_all_segment_aggregates,
)


def render_maintenance_dashboard() -> None:
    """Render the operations dashboard with periodic database refresh."""
    refresh_enabled = st.toggle("Live updates", value=True)
    refresh_interval = st.selectbox(
        "Refresh interval",
        options=[5, 15, 30, 60],
        index=1,
        format_func=lambda seconds: f"Every {seconds} seconds",
        disabled=not refresh_enabled,
    )
    run_every = f"{refresh_interval}s" if refresh_enabled else None

    @st.fragment(run_every=run_every)
    def render_live_dashboard() -> None:
        images = query_all_images()
        detections = query_all_detections()
        aggregates = query_all_segment_aggregates()
        avg_severity = (
            round(
                sum(float(d.get("severity_score", 0.0)) for d in detections)
                / len(detections),
                2,
            )
            if detections
            else 0.0
        )
        st.caption(
            "Live database view · Last refreshed "
            f"{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
        st.markdown("### 🧭 Maintenance Operations Dashboard")

        dashboard_view = st.radio(
            "Dashboard sections",
            [
                "Overview",
                "Priority Roads",
                "Road Crew Planner",
                "Budget",
                "Weekly Schedule",
                "Contractor Assignments",
                "Monthly Workload",
                "Action Plan",
            ],
            horizontal=True,
        )
        workers_per_crew = st.number_input(
            "Workers per repair crew",
            min_value=1,
            max_value=20,
            value=DEFAULT_WORKERS_PER_CREW,
            step=1,
        )
        st.caption(
            "Set a default crew size for schedules; in Road Crew Planner, "
            "adjust the worker count separately for each road."
        )

        if not aggregates:
            st.info("No maintenance plan yet. Process an image to generate repair planning data.")
            return

        agg_df = pd.DataFrame(aggregates)
        agg_df["priority_score"] = pd.to_numeric(
            agg_df.get("priority_score", 0), errors="coerce"
        ).fillna(0)
        agg_df["total_detections"] = pd.to_numeric(
            agg_df.get("total_detections", 0), errors="coerce"
        ).fillna(0)
        agg_df["max_severity"] = pd.to_numeric(
            agg_df.get("max_severity", 0), errors="coerce"
        ).fillna(0)

        total_cost = sum(
            float(aggregate.get("priority_score", 0.0)) * 120.0
            for aggregate in aggregates
        )
        projected_days = sum(
            estimated_completion_days(
                float(aggregate.get("priority_score", 0.0)), workers_per_crew
            )
            for aggregate in aggregates
        )
        avg_priority = float(agg_df["priority_score"].mean()) if not agg_df.empty else 0.0
        critical_roads = int((agg_df["priority_label"] == "critical").sum())
        high_roads = int(
            agg_df["priority_label"].isin(["critical", "high"]).sum()
        )

        if dashboard_view == "Overview":
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("💰 Planned Budget", f"${total_cost:,.0f}")
            m2.metric("🛠️ Projected Repair Days", f"{projected_days} days")
            m3.metric("🔴 Critical Roads", critical_roads)
            m4.metric("📈 Avg Priority", f"{avg_priority:.1f}")

            m5, m6, m7, m8 = st.columns(4)
            m5.metric("📷 Images Processed", len(images))
            m6.metric("🔍 Total Detections", len(detections))
            m7.metric("🛣️ Road Segments", len(aggregates))
            m8.metric("🚨 High Priority", high_roads)

            chart_col1, chart_col2 = st.columns(2)
            with chart_col1:
                damage_counts = Counter(
                    str(d.get("class_name", "unknown"))
                    .replace("_", " ")
                    .title()
                    for d in detections
                )
                damage_df = pd.DataFrame(
                    {
                        "Damage Type": list(damage_counts.keys()),
                        "Count": list(damage_counts.values()),
                    }
                )
                if not damage_df.empty:
                    st.subheader("Damage Type Distribution")
                    st.bar_chart(damage_df.set_index("Damage Type"), width="stretch")

            with chart_col2:
                priority_counts = Counter(
                    str(aggregate.get("priority_label", "low")).lower()
                    for aggregate in aggregates
                )
                priority_df = pd.DataFrame(
                    {
                        "Priority": list(priority_counts.keys()),
                        "Segments": list(priority_counts.values()),
                    }
                )
                if not priority_df.empty:
                    st.subheader("Priority Distribution")
                    st.bar_chart(priority_df.set_index("Priority"), width="stretch")

        elif dashboard_view == "Priority Roads":
            st.subheader("Top Priority Roads")
            top_roads = agg_df.sort_values(
                by="priority_score", ascending=False
            ).head(10)
            display_top = top_roads[
                [
                    "name",
                    "highway_type",
                    "priority_score",
                    "priority_label",
                    "total_detections",
                    "max_severity",
                ]
            ].copy()
            display_top.columns = [
                "Road Name",
                "Highway Type",
                "Priority Score",
                "Priority",
                "Detections",
                "Max Severity",
            ]
            st.dataframe(display_top, width="stretch", hide_index=True)

        elif dashboard_view == "Road Crew Planner":
            st.subheader("Road-by-road crew and completion estimate")
            crew_rows = []
            for index, aggregate in enumerate(aggregates, start=1):
                road_name = str(aggregate.get("name") or "").strip()
                if not road_name or road_name.lower() == "unknown road":
                    road_name = f"Road {index}"
                crew_rows.append(
                    {
                        "Road": road_name,
                        "Priority": str(
                            aggregate.get("priority_label", "low")
                        ).title(),
                        "Priority Score": float(
                            aggregate.get("priority_score", 0.0)
                        ),
                        "Detections": int(
                            aggregate.get("total_detections", 0)
                        ),
                        "Workers": int(workers_per_crew),
                    }
                )
            crew_plan = pd.DataFrame(crew_rows)
            edited_plan = st.data_editor(
                crew_plan,
                key="roadguard_road_crew_plan",
                width="stretch",
                hide_index=True,
                column_order=["Road", "Workers"],
                disabled=[
                    "Road",
                    "Priority",
                    "Priority Score",
                    "Detections",
                ],
                column_config={
                    "Road": st.column_config.TextColumn(width="small"),
                    "Workers": st.column_config.NumberColumn(
                        "Workers assigned",
                        min_value=1,
                        max_value=20,
                        step=1,
                        required=True,
                    ),
                    "Priority Score": st.column_config.NumberColumn(
                        format="%.1f"
                    ),
                },
            )
            edited_plan["Estimated Completion (days)"] = edited_plan.apply(
                lambda row: estimated_completion_days(
                    float(row["Priority Score"]), int(row["Workers"])
                ),
                axis=1,
            )
            st.caption("Completion estimates using the assigned worker counts:")
            st.dataframe(
                edited_plan[
                    [
                        "Road",
                        "Workers",
                        "Estimated Completion (days)",
                    ]
                ],
                width="stretch",
                hide_index=True,
                column_config={
                    "Road": st.column_config.TextColumn(width="small"),
                    "Workers": st.column_config.NumberColumn(width="small"),
                    "Estimated Completion (days)": st.column_config.NumberColumn(
                        "Days to completion", width="medium", format="%d"
                    ),
                },
            )
            st.caption(
                "Planning estimate: each road's baseline work is scaled from a "
                "four-worker crew. Actual completion depends on road length, "
                "materials, weather, and traffic management."
            )

        elif dashboard_view == "Budget":
            budget_summary = budget_summary_by_priority(aggregates)
            budget_rows = [
                {
                    "Priority": label,
                    "Total Cost": float(values["total_cost"]),
                    "Crew Days": int(values["crew_days"]),
                }
                for label, values in budget_summary.items()
            ]
            if budget_rows:
                budget_df = pd.DataFrame(budget_rows)
                st.subheader("💸 Priority Budget Summary")
                st.bar_chart(budget_df.set_index("Priority"), width="stretch")
                st.dataframe(budget_df, width="stretch", hide_index=True)
            else:
                st.info("No budget summary yet.")

        elif dashboard_view == "Weekly Schedule":
            schedule_df = pd.DataFrame(
                schedule_repair_plan(
                    aggregates, workers_per_crew=workers_per_crew
                )
            )
            if not schedule_df.empty:
                st.subheader("📅 Weekly Repair Schedule")
                schedule_df = schedule_df[
                    [
                        "name",
                        "priority_score",
                        "priority_label",
                        "week",
                        "repair_window",
                        "workers_needed",
                        "completion_days",
                    ]
                ]
                schedule_df.columns = [
                    "Road",
                    "Priority Score",
                    "Priority",
                    "Week",
                    "Repair Window",
                    "Workers",
                    "Completion Days",
                ]
                st.dataframe(schedule_df, width="stretch", hide_index=True)
            else:
                st.info("No weekly schedule yet.")

        elif dashboard_view == "Contractor Assignments":
            contractor_df = pd.DataFrame(
                assign_contractors(
                    aggregates, workers_per_crew=workers_per_crew
                )
            )
            if not contractor_df.empty:
                st.subheader("👷 Contractor Assignment Board")
                contractor_df = contractor_df[
                    [
                        "name",
                        "priority_score",
                        "priority_label",
                        "team",
                        "workers_needed",
                        "completion_days",
                    ]
                ]
                contractor_df.columns = [
                    "Road",
                    "Priority Score",
                    "Priority",
                    "Assigned Team",
                    "Workers",
                    "Completion Days",
                ]
                st.dataframe(contractor_df, width="stretch", hide_index=True)
                team_plan = (
                    contractor_df.groupby("Assigned Team", as_index=False)[
                        "Completion Days"
                    ]
                    .sum()
                    .rename(columns={"Assigned Team": "Team"})
                )
                st.bar_chart(team_plan.set_index("Team"), width="stretch")
            else:
                st.info("No contractor assignments yet.")

        elif dashboard_view == "Monthly Workload":
            monthly_plan = pd.DataFrame(
                build_monthly_schedule(
                    aggregates, workers_per_crew=workers_per_crew
                )
            )
            if not monthly_plan.empty:
                monthly_workload = (
                    monthly_plan.groupby("month", as_index=False)["crew_days"]
                    .sum()
                    .rename(columns={"month": "Month", "crew_days": "Crew Days"})
                )
                st.subheader("🗓️ Monthly Workload")
                st.bar_chart(monthly_workload.set_index("Month"), width="stretch")
                st.dataframe(
                    monthly_plan[
                        [
                            "name",
                            "priority_score",
                            "priority_label",
                            "month",
                            "repair_window",
                            "workers_needed",
                            "completion_days",
                        ]
                    ].rename(
                        columns={
                            "name": "Road",
                            "priority_score": "Priority Score",
                            "priority_label": "Priority",
                            "month": "Month",
                            "repair_window": "Repair Window",
                            "workers_needed": "Workers",
                            "completion_days": "Completion Days",
                        }
                    ),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info("No monthly workload yet.")

        elif dashboard_view == "Action Plan":
            st.subheader("🧾 Maintenance Action Plan")
            plan_df = pd.DataFrame(
                build_maintenance_plan(
                    aggregates, workers_per_crew=workers_per_crew
                )
            )
            if not plan_df.empty:
                plan_df = plan_df[
                    [
                        "name",
                        "highway_type",
                        "priority_score",
                        "action",
                        "repair_window",
                        "estimated_cost",
                        "workers_needed",
                        "completion_days",
                    ]
                ]
                plan_df.columns = [
                    "Road",
                    "Type",
                    "Priority",
                    "Action",
                    "Repair Window",
                    "Est. Cost",
                    "Workers",
                    "Completion Days",
                ]
                st.dataframe(plan_df, width="stretch", hide_index=True)
            else:
                st.info("No action plan yet.")

        contractor_plan = assign_contractors(aggregates)
        top_priority = max(
            (float(aggregate.get("priority_score", 0.0)) for aggregate in aggregates),
            default=0.0,
        )
        action = (
            "Immediate repair"
            if top_priority >= 75
            else "Scheduled repair"
            if top_priority >= 50
            else "Monitor and repair soon"
            if top_priority >= 25
            else "Routine inspection"
        )
        planner1, planner2, planner3 = st.columns(3)
        planner1.metric("⏱️ Recommended Action", action)
        planner2.metric("📉 Avg Severity", f"{avg_severity:.2f}")
        planner3.metric(
            "🧑‍🔧 Active Teams",
            len({row.get("team", "Routine Patrol Crew") for row in contractor_plan}),
        )

    render_live_dashboard()
