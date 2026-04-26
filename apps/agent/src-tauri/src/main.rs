use chrono::{DateTime, SecondsFormat, Utc};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs;
use std::path::PathBuf;
use std::time::Duration;
use tauri::{AppHandle, Manager};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AgentDesktopRuntimeConfig {
    api_base_url: String,
    method_dev_base_url: String,
    operator_mode_enabled: bool,
    cache_policy: String,
    demo_snapshot_version: String,
    startup_health_ttl_sec: u64,
}

impl Default for AgentDesktopRuntimeConfig {
    fn default() -> Self {
        Self {
            api_base_url: "http://127.0.0.1:8000".to_string(),
            method_dev_base_url: "http://127.0.0.1:8001".to_string(),
            operator_mode_enabled: false,
            cache_policy: "live_preferred".to_string(),
            demo_snapshot_version: "2026-04-18".to_string(),
            startup_health_ttl_sec: 30,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AgentServiceHealth {
    status: String,
    checked_at: String,
    endpoint: String,
    response_time_ms: Option<u64>,
    detail: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AgentStartupHealth {
    status: String,
    checked_at: String,
    cached: bool,
    api: AgentServiceHealth,
    method_dev: AgentServiceHealth,
}

fn app_data_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let app_data_dir = app
        .path()
        .app_data_dir()
        .map_err(|error| format!("Unable to resolve app data dir: {error}"))?;
    fs::create_dir_all(&app_data_dir)
        .map_err(|error| format!("Unable to create app data dir: {error}"))?;
    Ok(app_data_dir)
}

fn runtime_config_path(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(app_data_dir(app)?.join("agent-runtime-config.json"))
}

fn startup_health_cache_path(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(app_data_dir(app)?.join("agent-startup-health.json"))
}

fn normalize_base_url(raw: &str) -> String {
    raw.trim().trim_end_matches('/').to_string()
}

fn normalize_cache_policy(raw: &str) -> String {
    match raw.trim() {
        "cached_preferred" => "cached_preferred".to_string(),
        "demo_safe" => "demo_safe".to_string(),
        _ => "live_preferred".to_string(),
    }
}

fn parse_env_bool(name: &str) -> Option<bool> {
    std::env::var(name).ok().and_then(|value| {
        let normalized = value.trim().to_ascii_lowercase();
        if ["1", "true", "yes", "on"].contains(&normalized.as_str()) {
            Some(true)
        } else if ["0", "false", "no", "off"].contains(&normalized.as_str()) {
            Some(false)
        } else {
            None
        }
    })
}

fn parse_env_u64(name: &str) -> Option<u64> {
    std::env::var(name)
        .ok()
        .and_then(|value| value.trim().parse::<u64>().ok())
}

fn parse_env_string(name: &str) -> Option<String> {
    std::env::var(name).ok().and_then(|value| {
        let trimmed = value.trim();
        if trimmed.is_empty() {
            None
        } else {
            Some(trimmed.to_string())
        }
    })
}

fn normalize_runtime_config(raw: AgentDesktopRuntimeConfig) -> AgentDesktopRuntimeConfig {
    AgentDesktopRuntimeConfig {
        api_base_url: normalize_base_url(&raw.api_base_url),
        method_dev_base_url: normalize_base_url(&raw.method_dev_base_url),
        operator_mode_enabled: raw.operator_mode_enabled,
        cache_policy: normalize_cache_policy(&raw.cache_policy),
        demo_snapshot_version: if raw.demo_snapshot_version.trim().is_empty() {
            AgentDesktopRuntimeConfig::default().demo_snapshot_version
        } else {
            raw.demo_snapshot_version.trim().to_string()
        },
        startup_health_ttl_sec: raw.startup_health_ttl_sec.max(5),
    }
}

fn apply_env_overrides(config: AgentDesktopRuntimeConfig) -> AgentDesktopRuntimeConfig {
    normalize_runtime_config(AgentDesktopRuntimeConfig {
        api_base_url: parse_env_string("SILICO_AGENT_API_BASE_URL")
            .unwrap_or(config.api_base_url),
        method_dev_base_url: parse_env_string("SILICO_AGENT_METHOD_DEV_BASE_URL")
            .unwrap_or(config.method_dev_base_url),
        operator_mode_enabled: parse_env_bool("SILICO_AGENT_OPERATOR_MODE_ENABLED")
            .unwrap_or(config.operator_mode_enabled),
        cache_policy: parse_env_string("SILICO_AGENT_CACHE_POLICY")
            .unwrap_or(config.cache_policy),
        demo_snapshot_version: parse_env_string("SILICO_AGENT_DEMO_SNAPSHOT_VERSION")
            .unwrap_or(config.demo_snapshot_version),
        startup_health_ttl_sec: parse_env_u64("SILICO_AGENT_STARTUP_HEALTH_TTL_SEC")
            .unwrap_or(config.startup_health_ttl_sec),
    })
}

fn load_runtime_config(app: &AppHandle) -> Result<AgentDesktopRuntimeConfig, String> {
    let path = runtime_config_path(app)?;
    let persisted = if path.exists() {
        let raw = fs::read_to_string(&path)
            .map_err(|error| format!("Unable to read runtime config: {error}"))?;
        serde_json::from_str::<AgentDesktopRuntimeConfig>(&raw)
            .map_err(|error| format!("Unable to parse runtime config: {error}"))?
    } else {
        AgentDesktopRuntimeConfig::default()
    };

    Ok(apply_env_overrides(persisted))
}

fn save_runtime_config(app: &AppHandle, config: &AgentDesktopRuntimeConfig) -> Result<(), String> {
    let normalized = normalize_runtime_config(config.clone());
    let path = runtime_config_path(app)?;
    let payload = serde_json::to_string_pretty(&normalized)
        .map_err(|error| format!("Unable to serialize runtime config: {error}"))?;
    fs::write(path, payload).map_err(|error| format!("Unable to persist runtime config: {error}"))?;
    Ok(())
}

fn save_startup_health_cache(app: &AppHandle, health: &AgentStartupHealth) -> Result<(), String> {
    let path = startup_health_cache_path(app)?;
    let payload = serde_json::to_string_pretty(health)
        .map_err(|error| format!("Unable to serialize startup health: {error}"))?;
    fs::write(path, payload)
        .map_err(|error| format!("Unable to persist startup health cache: {error}"))?;
    Ok(())
}

fn load_startup_health_cache(app: &AppHandle) -> Result<Option<AgentStartupHealth>, String> {
    let path = startup_health_cache_path(app)?;
    if !path.exists() {
        return Ok(None);
    }

    let raw =
        fs::read_to_string(path).map_err(|error| format!("Unable to read startup health cache: {error}"))?;
    let parsed = serde_json::from_str::<AgentStartupHealth>(&raw)
        .map_err(|error| format!("Unable to parse startup health cache: {error}"))?;
    Ok(Some(parsed))
}

fn join_base_and_path(base_url: &str, path: &str) -> String {
    format!("{}/{}", normalize_base_url(base_url), path.trim_start_matches('/'))
}

fn combine_health_statuses(api_status: &str, method_dev_status: &str) -> String {
    if api_status == "healthy" && method_dev_status == "healthy" {
        return "healthy".to_string();
    }

    if api_status == "unavailable" && method_dev_status == "unavailable" {
        return "unavailable".to_string();
    }

    "degraded".to_string()
}

fn is_cached_health_fresh(
    cached: &AgentStartupHealth,
    config: &AgentDesktopRuntimeConfig,
) -> bool {
    if cached.api.endpoint != join_base_and_path(&config.api_base_url, "/api/health")
        || cached.method_dev.endpoint != join_base_and_path(&config.method_dev_base_url, "/health")
    {
        return false;
    }

    let checked_at = match DateTime::parse_from_rfc3339(&cached.checked_at) {
        Ok(value) => value.with_timezone(&Utc),
        Err(_) => return false,
    };

    let age_seconds = Utc::now()
        .signed_duration_since(checked_at)
        .num_seconds();
    age_seconds >= 0 && (age_seconds as u64) <= config.startup_health_ttl_sec
}

async fn check_service_health(
    client: &Client,
    endpoint: String,
    classify: impl FnOnce(Option<Value>) -> (String, Option<String>),
) -> AgentServiceHealth {
    let started_at = std::time::Instant::now();
    match client.get(&endpoint).send().await {
        Ok(response) => {
            let duration_ms = started_at.elapsed().as_millis() as u64;
            if !response.status().is_success() {
                return AgentServiceHealth {
                    status: "unavailable".to_string(),
                    checked_at: Utc::now().to_rfc3339_opts(SecondsFormat::Millis, true),
                    endpoint,
                    response_time_ms: Some(duration_ms),
                    detail: Some(format!("HTTP {}", response.status().as_u16())),
                };
            }

            let payload = response.json::<Value>().await.ok();
            let (status, detail) = classify(payload);
            AgentServiceHealth {
                status,
                checked_at: Utc::now().to_rfc3339_opts(SecondsFormat::Millis, true),
                endpoint,
                response_time_ms: Some(duration_ms),
                detail,
            }
        }
        Err(error) => AgentServiceHealth {
            status: "unavailable".to_string(),
            checked_at: Utc::now().to_rfc3339_opts(SecondsFormat::Millis, true),
            endpoint,
            response_time_ms: Some(started_at.elapsed().as_millis() as u64),
            detail: Some(error.to_string()),
        },
    }
}

async fn collect_startup_health(
    config: &AgentDesktopRuntimeConfig,
) -> Result<AgentStartupHealth, String> {
    let client = Client::builder()
        .timeout(Duration::from_secs(4))
        .build()
        .map_err(|error| format!("Unable to build health-check client: {error}"))?;

    let api_endpoint = join_base_and_path(&config.api_base_url, "/api/health");
    let method_dev_endpoint = join_base_and_path(&config.method_dev_base_url, "/health");

    let api_check = check_service_health(&client, api_endpoint, |payload| {
        let status = payload
            .as_ref()
            .and_then(|value| value.get("status"))
            .and_then(Value::as_str);
        match status {
            Some("ok") | Some("ready") => ("healthy".to_string(), None),
            Some(other) => ("degraded".to_string(), Some(format!("status={other}"))),
            None => (
                "degraded".to_string(),
                Some("Unexpected API health payload".to_string()),
            ),
        }
    });
    let method_dev_check = check_service_health(&client, method_dev_endpoint, |payload| {
        let status = payload
            .as_ref()
            .and_then(|value| value.get("status"))
            .and_then(Value::as_str);
        let retrieval_store = payload
            .as_ref()
            .and_then(|value| value.get("retrieval_store"))
            .and_then(Value::as_str);

        if status == Some("ok") && retrieval_store == Some("ready") {
            return ("healthy".to_string(), None);
        }

        let mut details = Vec::new();
        if let Some(value) = status {
            details.push(format!("status={value}"));
        }
        if let Some(value) = retrieval_store {
            details.push(format!("retrieval_store={value}"));
        }

        (
            "degraded".to_string(),
            Some(if details.is_empty() {
                "Unexpected method-dev health payload".to_string()
            } else {
                details.join(", ")
            }),
        )
    });

    let (api, method_dev) = tokio::join!(api_check, method_dev_check);

    Ok(AgentStartupHealth {
        status: combine_health_statuses(&api.status, &method_dev.status),
        checked_at: Utc::now().to_rfc3339_opts(SecondsFormat::Millis, true),
        cached: false,
        api,
        method_dev,
    })
}

#[tauri::command]
fn get_agent_runtime_config(app: AppHandle) -> Result<AgentDesktopRuntimeConfig, String> {
    load_runtime_config(&app)
}

#[tauri::command]
fn set_agent_runtime_config(
    app: AppHandle,
    config: AgentDesktopRuntimeConfig,
) -> Result<AgentDesktopRuntimeConfig, String> {
    let normalized = normalize_runtime_config(config);
    save_runtime_config(&app, &normalized)?;
    Ok(apply_env_overrides(normalized))
}

#[tauri::command]
async fn get_agent_startup_health(app: AppHandle) -> Result<AgentStartupHealth, String> {
    let config = load_runtime_config(&app)?;

    if let Some(mut cached) = load_startup_health_cache(&app)? {
        if is_cached_health_fresh(&cached, &config) {
            cached.cached = true;
            return Ok(cached);
        }
    }

    let health = collect_startup_health(&config).await?;
    save_startup_health_cache(&app, &health)?;
    Ok(health)
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_agent_runtime_config,
            set_agent_runtime_config,
            get_agent_startup_health
        ])
        .run(tauri::generate_context!())
        .expect("error while running Silico Agent desktop shell");
}
