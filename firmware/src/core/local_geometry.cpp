// SPDX-License-Identifier: AGPL-3.0-only
#include "local_geometry.hpp"
#include <algorithm>
#include <cmath>

namespace sonar::local {
namespace {
constexpr double half_pi = 1.57079632679489661923;
void add(Result& r, Reason why) noexcept {
    for(auto& s:r.sectors) s.reasons |= static_cast<Reasons>(why);
}
bool finite(Vec3 v) noexcept { return std::isfinite(v.x) && std::isfinite(v.y) && std::isfinite(v.z); }
double norm(Vec3 v) noexcept { return std::hypot(v.x,v.y,v.z); }
bool unit(Vec3 v,double tol) noexcept { return finite(v) && std::abs(norm(v)-1)<=tol; }
Vec3 rotate(const Matrix3& r,Vec3 v) noexcept {
    return {r[0][0]*v.x+r[0][1]*v.y+r[0][2]*v.z,
            r[1][0]*v.x+r[1][1]*v.y+r[1][2]*v.z,
            r[2][0]*v.x+r[2][1]*v.y+r[2][2]*v.z};
}
bool proper(const Matrix3& r,double tol) noexcept {
    for(const auto& row:r) if(!unit({row[0],row[1],row[2]},tol)) return false;
    for(std::size_t i=0;i<3;++i) for(std::size_t j=i+1;j<3;++j) {
        double dot=0; for(std::size_t k=0;k<3;++k) dot+=r[i][k]*r[j][k];
        if(!std::isfinite(dot) || std::abs(dot)>tol) return false;
    }
    const auto determinant=r[0][0]*(r[1][1]*r[2][2]-r[1][2]*r[2][1])
                         -r[0][1]*(r[1][0]*r[2][2]-r[1][2]*r[2][0])
                         +r[0][2]*(r[1][0]*r[2][1]-r[1][1]*r[2][0]);
    return std::isfinite(determinant) && std::abs(determinant-1)<=tol;
}
bool valid(const GeometryProfile& g) noexcept {
    return g.id && g.max_tof_age_us && g.max_imu_age_us && g.dt_min_us && g.dt_min_us<=g.dt_max_us
        && std::isfinite(g.center_half_angle_rad) && g.center_half_angle_rad>0 && g.center_half_angle_rad<half_pi
        && std::isfinite(g.z_min_m) && std::isfinite(g.z_max_m) && g.z_min_m<=g.z_max_m
        && std::isfinite(g.unit_norm_tolerance) && g.unit_norm_tolerance>0 && g.unit_norm_tolerance<1;
}
bool valid(const RiskProfile* r) noexcept {
    return r && r->id && r->stage==Stage::fixture
        && std::isfinite(r->urgent_range_m) && r->urgent_range_m>0
        && std::isfinite(r->attention_range_m) && r->urgent_range_m<r->attention_range_m
        && std::isfinite(r->protection_range_m) && r->protection_range_m>=0
        && std::isfinite(r->min_closing_rate_m_s) && r->min_closing_rate_m_s>=0;
}
bool same(Vec3 a,Vec3 b) noexcept { return a.x==b.x && a.y==b.y && a.z==b.z; }
bool same(const Calibration& a,const Calibration& b) noexcept {
    if(a.id!=b.id || a.distance_kind!=b.distance_kind || a.tof_to_head!=b.tof_to_head || !same(a.translation_tof_to_head,b.translation_tof_to_head)) return false;
    for(std::size_t i=0;i<zone_count;++i) if(!same(a.unit_rays[i],b.unit_rays[i])) return false;
    return true;
}
bool same(const GeometryProfile& a,const GeometryProfile& b) noexcept {
    return a.id==b.id && a.max_tof_age_us==b.max_tof_age_us && a.max_imu_age_us==b.max_imu_age_us
        && a.max_skew_us==b.max_skew_us && a.dt_min_us==b.dt_min_us && a.dt_max_us==b.dt_max_us
        && a.center_half_angle_rad==b.center_half_angle_rad && a.z_min_m==b.z_min_m
        && a.z_max_m==b.z_max_m && a.unit_norm_tolerance==b.unit_norm_tolerance;
}
bool same(const std::optional<RiskProfile>& a,const RiskProfile* b) noexcept {
    if(!a || !b) return !a && !b;
    return a->id==b->id && a->stage==b->stage && a->urgent_range_m==b->urgent_range_m
        && a->attention_range_m==b->attention_range_m && a->protection_range_m==b->protection_range_m
        && a->min_closing_rate_m_s==b->min_closing_rate_m_s;
}
bool timestamp(Time captured,Time now,Time limit,Result& r) noexcept {
    if(captured>now) { add(r,Reason::future); return false; }
    if(now-captured>=limit) { add(r,Reason::stale); return false; }
    return true;
}
bool association_valid(const FixtureAssociation* a) noexcept {
    if(!a || a->source!=AssociationSource::controlled_fixture_same_point || a->count>zone_count) return false;
    std::array<bool,zone_count> current{}, previous{};
    for(std::size_t i=0;i<a->count;++i) {
        const auto& link=a->links[i];
        if(link.current_zone>=zone_count || link.previous_zone>=zone_count || !link.point_id
           || current[link.current_zone] || previous[link.previous_zone]) return false;
        // A declared physical point cannot occupy two links in one acquisition.
        for(std::size_t j=0;j<i;++j) if(a->links[j].point_id==link.point_id) return false;
        current[link.current_zone]=true; previous[link.previous_zone]=true;
    }
    return true;
}
} // namespace

Result update(const Input& in,State& state) noexcept {
    Result out{};
    out.boot_session=in.boot_session;
    out.sectors[0].sector=Sector::left; out.sectors[1].sector=Sector::center; out.sectors[2].sector=Sector::right;
    if(in.tof) { out.acquisition_id=in.tof->acquisition_id; out.captured_at_us=in.tof->captured_at_us; }
    if(in.orientation) { out.reference_id=in.orientation->reference_id; out.orientation_at_us=in.orientation->captured_at_us; }
    if(in.calibration) out.calibration_id=in.calibration->id;
    if(in.geometry_profile) out.geometry_profile_id=in.geometry_profile->id;
    if(in.risk_profile) out.risk_profile_id=in.risk_profile->id;
    const bool risk_ok=valid(in.risk_profile);
    if(!risk_ok) add(out,Reason::risk_unconfigured);
    const bool regressed=state.has_clock && state.boot_session==in.boot_session && in.now_us<state.now_us;
    if(regressed) { add(out,Reason::clock_regression); state.has_history=false; }
    state.has_clock=true; state.now_us=in.now_us;
    // Clock session is tracked even through unavailable samples.
    if(state.boot_session!=in.boot_session) {
        if(state.has_history) add(out,Reason::continuity_reset);
        state.has_history=false; state.boot_session=in.boot_session;
    }
    const auto reject=[&](Reason reason) noexcept {
        add(out,reason); add(out,Reason::no_observation); state.has_history=false; return out;
    };
    if(!in.boot_session || !in.geometry_profile || !valid(*in.geometry_profile)) return reject(Reason::configuration);
    const auto& g=*in.geometry_profile;
    if(!in.calibration || !in.calibration->id || !finite(in.calibration->translation_tof_to_head)
       || !proper(in.calibration->tof_to_head,g.unit_norm_tolerance)) return reject(Reason::calibration);
    const auto& c=*in.calibration;
    if(c.distance_kind!=DistanceKind::radial) return reject(Reason::distance_kind);
    if(!in.tof) return reject(Reason::no_frame);
    const auto& frame=*in.tof;
    if(frame.boot_session!=in.boot_session) return reject(Reason::session);
    if(frame.calibration_id!=c.id) return reject(Reason::calibration);
    if(frame.distance_kind!=DistanceKind::radial) return reject(Reason::distance_kind);
    std::array<bool,zone_count> indices{};
    for(const auto& zone:frame.zones) {
        if(zone.index>=zone_count || indices[zone.index]) return reject(Reason::frame_structure);
        indices[zone.index]=true;
    }
    if(!in.orientation) return reject(Reason::no_orientation);
    const auto& orientation=*in.orientation;
    if(orientation.boot_session!=in.boot_session) return reject(Reason::session);
    if(!orientation.reference_id || orientation.quality!=OrientationQuality::usable) return reject(Reason::orientation);
    if(!timestamp(frame.captured_at_us,in.now_us,g.max_tof_age_us,out)
       || !timestamp(orientation.captured_at_us,in.now_us,g.max_imu_age_us,out)) return reject(Reason::no_observation);
    const Time skew=std::max(frame.captured_at_us,orientation.captured_at_us)-std::min(frame.captured_at_us,orientation.captured_at_us);
    if(skew>g.max_skew_us) return reject(Reason::skew);
    auto q=orientation.head_to_reference_wxyz;
    for(double value:q) if(!std::isfinite(value)) return reject(Reason::orientation);
    const double qnorm=std::hypot(std::hypot(q[0],q[1]),std::hypot(q[2],q[3]));
    if(!std::isfinite(qnorm) || qnorm==0 || std::abs(qnorm-1)>g.unit_norm_tolerance) return reject(Reason::orientation);
    for(double& value:q) value/=qnorm;
    const double w=q[0], x=q[1], y=q[2], z=q[3];
    const Matrix3 head_to_reference{{{1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)},
                                    {2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)},
                                    {2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)}}};
    if(state.has_history && (state.reference_id!=orientation.reference_id || !same(state.calibration,c)
        || !same(state.geometry_profile,g) || !same(state.risk_profile,in.risk_profile))) {
        state.has_history=false; add(out,Reason::continuity_reset);
    }
    const bool duplicate=state.has_history && frame.acquisition_id==state.acquisition_id;
    bool capture_regression=false;
    if(duplicate) add(out,Reason::duplicate);
    else if(state.has_history && (frame.captured_at_us<=state.captured_at_us || frame.acquisition_id<state.acquisition_id)) {
        capture_regression=true; state.has_history=false; add(out,Reason::clock_regression);
    }
    std::array<std::optional<double>,zone_count> current{};
    std::size_t usable=0, excluded=0;
    // Index-normalized traversal makes ties and results independent of zone array order.
    std::array<const Zone*,zone_count> zones{};
    for(const auto& zone:frame.zones) zones[zone.index]=&zone;
    for(std::size_t i=0;i<zone_count;++i) {
        const auto& zone=*zones[i]; const auto ray=c.unit_rays[i];
        if(zone.quality!=ZoneQuality::usable || !zone.radial_range_m || !std::isfinite(*zone.radial_range_m)
           || *zone.radial_range_m<=0 || !unit(ray,g.unit_norm_tolerance)) { add(out,Reason::invalid_zone); continue; }
        const double range=*zone.radial_range_m;
        Vec3 head=rotate(c.tof_to_head,{range*ray.x,range*ray.y,range*ray.z});
        head.x+=c.translation_tof_to_head.x; head.y+=c.translation_tof_to_head.y; head.z+=c.translation_tof_to_head.z;
        const Vec3 point=rotate(head_to_reference,head);
        if(!finite(head) || !finite(point)) { add(out,Reason::numerical); continue; }
        ++usable;
        if(point.x<=0 || point.z<g.z_min_m || point.z>g.z_max_m) { ++excluded; add(out,Reason::excluded); continue; }
        current[i]=range;
        const double angle=std::atan2(point.y,point.x);
        const std::size_t sector=angle>g.center_half_angle_rad?0:(angle < -g.center_half_angle_rad?2:1);
        auto& s=out.sectors[sector]; ++s.coverage.projected_in_sector;
        if(!s.nearest_observed_range_m || range<*s.nearest_observed_range_m) {
            s.nearest_observed_range_m=range; s.source_zone=static_cast<std::uint8_t>(i);
        }
    }
    const bool paired=state.has_history && !duplicate && !regressed && !capture_regression;
    Time dt=0;
    bool interval_ok=false;
    if(paired) { dt=frame.captured_at_us-state.captured_at_us; interval_ok=dt>=g.dt_min_us && dt<=g.dt_max_us; }
    const bool links_ok=paired && association_valid(in.association) && in.association->previous_acquisition_id==state.acquisition_id;
    for(auto& s:out.sectors) {
        s.coverage.frame_usable=usable; s.coverage.frame_invalid=zone_count-usable;
        if(!s.nearest_observed_range_m) { s.reasons|=static_cast<Reasons>(Reason::no_observation); continue; }
        s.assessment=risk_ok ? ((usable<zone_count || excluded)?Assessment::limited:Assessment::known) : Assessment::unconfigured;
        if(risk_ok) {
            const auto& risk=*in.risk_profile; const double range=*s.nearest_observed_range_m;
            s.observed_band=range<=risk.urgent_range_m?Band::urgent:(range<=risk.attention_range_m?Band::attention:Band::outside_thresholds);
        }
        if(!paired) { s.reasons|=static_cast<Reasons>(Reason::no_history); continue; }
        if(!interval_ok) { s.reasons|=static_cast<Reasons>(Reason::interval); continue; }
        if(!links_ok) { s.reasons|=static_cast<Reasons>(Reason::association); continue; }
        const Link* link=nullptr;
        for(std::size_t i=0;i<in.association->count;++i)
            if(in.association->links[i].current_zone==*s.source_zone) { link=&in.association->links[i]; break; }
        if(!link || !state.ranges[link->previous_zone]) { s.reasons|=static_cast<Reasons>(Reason::association); continue; }
        const double rate=(*state.ranges[link->previous_zone]-*s.nearest_observed_range_m)/(static_cast<double>(dt)/1000000.0);
        if(!std::isfinite(rate)) { s.reasons|=static_cast<Reasons>(Reason::numerical); continue; }
        s.closing_rate_m_s=rate; s.motion_basis=MotionBasis::controlled_fixture;
        if(!risk_ok) continue;
        if(rate<=in.risk_profile->min_closing_rate_m_s) { s.reasons|=static_cast<Reasons>(Reason::not_closing); continue; }
        const double ttc=*s.nearest_observed_range_m/rate;
        const double protection=std::max(0.0,*s.nearest_observed_range_m-in.risk_profile->protection_range_m)/rate;
        if(std::isfinite(ttc) && std::isfinite(protection)) { s.radial_ttc_candidate_s=ttc; s.time_to_protection_s=protection; }
        else s.reasons|=static_cast<Reasons>(Reason::numerical);
    }
    // Duplicates cannot poison the previous ranges. Regressions never become a baseline.
    if(!duplicate && !regressed && !capture_regression && usable>excluded) {
        state.has_history=true; state.boot_session=in.boot_session; state.reference_id=orientation.reference_id;
        state.acquisition_id=frame.acquisition_id; state.captured_at_us=frame.captured_at_us;
        state.calibration=c; state.geometry_profile=g;
        state.risk_profile=in.risk_profile?std::optional<RiskProfile>{*in.risk_profile}:std::nullopt;
        state.ranges=current;
    } else if(!duplicate) state.has_history=false;
    return out;
}
} // namespace sonar::local
