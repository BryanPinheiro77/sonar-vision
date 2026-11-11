// SPDX-License-Identifier: AGPL-3.0-only
#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>

namespace sonar::local {
constexpr std::size_t zone_count = 64;
using Id = std::uint64_t;
using Time = std::uint64_t;
struct Vec3 { double x{}, y{}, z{}; };
using Matrix3 = std::array<std::array<double, 3>, 3>;
enum class DistanceKind { unknown, radial, axial };
enum class ZoneQuality { usable, missing, invalid, no_return };
enum class OrientationQuality { usable, missing, unreliable };
enum class Stage { unapproved, fixture };
enum class Sector { left, center, right };
enum class Assessment { known, limited, unavailable, unconfigured };
enum class Band { outside_thresholds, attention, urgent };
enum class MotionBasis { unsupported, controlled_fixture };
enum class AssociationSource { unknown, controlled_fixture_same_point };
enum class Reason : std::uint64_t {
    configuration = 1ULL << 0, no_frame = 1ULL << 1,
    frame_structure = 1ULL << 2, session = 1ULL << 3,
    calibration = 1ULL << 4, distance_kind = 1ULL << 5,
    no_orientation = 1ULL << 6, orientation = 1ULL << 7,
    future = 1ULL << 8, stale = 1ULL << 9, skew = 1ULL << 10,
    invalid_zone = 1ULL << 11, excluded = 1ULL << 12,
    no_observation = 1ULL << 13, risk_unconfigured = 1ULL << 14,
    no_history = 1ULL << 15, duplicate = 1ULL << 16,
    clock_regression = 1ULL << 17, continuity_reset = 1ULL << 18,
    interval = 1ULL << 19, association = 1ULL << 20,
    not_closing = 1ULL << 21, numerical = 1ULL << 22
};
using Reasons = std::uint64_t;
constexpr bool has(Reasons reasons, Reason reason) noexcept {
    return (reasons & static_cast<Reasons>(reason)) != 0;
}
struct Zone {
    std::uint8_t index{};
    std::optional<double> radial_range_m{};
    ZoneQuality quality{ZoneQuality::missing};
};
struct ToFFrame {
    Id boot_session{}, acquisition_id{}, calibration_id{};
    Time captured_at_us{};
    DistanceKind distance_kind{DistanceKind::unknown};
    std::array<Zone, zone_count> zones{};
};
struct Orientation {
    Id boot_session{}, reference_id{};
    Time captured_at_us{};
    OrientationQuality quality{OrientationQuality::missing};
    std::array<double, 4> head_to_reference_wxyz{};
};
struct Calibration {
    Id id{};
    DistanceKind distance_kind{DistanceKind::unknown};
    std::array<Vec3, zone_count> unit_rays{};
    Matrix3 tof_to_head{};
    Vec3 translation_tof_to_head{};
};
struct GeometryProfile {
    Id id{};
    Time max_tof_age_us{}, max_imu_age_us{}, max_skew_us{}, dt_min_us{}, dt_max_us{};
    double center_half_angle_rad{}, z_min_m{}, z_max_m{}, unit_norm_tolerance{};
};
struct RiskProfile {
    Id id{};
    Stage stage{Stage::unapproved};
    double urgent_range_m{}, attention_range_m{}, protection_range_m{}, min_closing_rate_m_s{};
};
struct Link { std::uint8_t current_zone{}, previous_zone{}; Id point_id{}; };
struct FixtureAssociation {
    AssociationSource source{AssociationSource::unknown};
    Id previous_acquisition_id{};
    std::size_t count{};
    std::array<Link, zone_count> links{};
};
struct Input {
    Id boot_session{};
    Time now_us{};
    const ToFFrame* tof{};
    const Orientation* orientation{};
    const Calibration* calibration{};
    const GeometryProfile* geometry_profile{};
    const RiskProfile* risk_profile{};
    const FixtureAssociation* association{};
};
struct Coverage {
    std::size_t frame_zones{zone_count}, frame_usable{}, frame_invalid{zone_count}, projected_in_sector{};
};
struct SectorResult {
    Sector sector{};
    Assessment assessment{Assessment::unavailable};
    Reasons reasons{};
    Coverage coverage{};
    std::optional<std::uint8_t> source_zone{};
    std::optional<double> nearest_observed_range_m{}, closing_rate_m_s{};
    std::optional<double> radial_ttc_candidate_s{}, time_to_protection_s{};
    std::optional<Band> observed_band{};
    MotionBasis motion_basis{MotionBasis::unsupported};
};
struct Result {
    Id boot_session{}, reference_id{}, calibration_id{}, geometry_profile_id{};
    std::optional<Id> acquisition_id{}, risk_profile_id{};
    std::optional<Time> captured_at_us{}, orientation_at_us{};
    std::array<SectorResult, 3> sectors{};
};
// Caller owns all storage. Only one previous acquisition (64 records) is kept.
// Configuration snapshots detect changes even if a caller accidentally reuses an ID.
struct State {
    bool has_clock{}, has_history{};
    Id boot_session{}, reference_id{}, acquisition_id{};
    Time now_us{}, captured_at_us{};
    Calibration calibration{};
    GeometryProfile geometry_profile{};
    std::optional<RiskProfile> risk_profile{};
    std::array<std::optional<double>, zone_count> ranges{};
};
Result update(const Input& input, State& state) noexcept;
} // namespace sonar::local
